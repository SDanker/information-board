"use client";

import { use, useEffect, useRef, useState } from "react";
import { Activity, CalendarDays, Clock3, MapPin, Radio, WifiOff } from "lucide-react";

import BrandMark from "@/components/BrandMark";
import { API_BASE, CalendarEvent, CalendarFeed, wsUrl } from "@/lib/api";
import { DisplaySettings, useBranding, useDisplaySettings } from "@/lib/branding";
import { CALENDAR_POLL_INTERVAL_MS, HEARTBEAT_INTERVAL_MS, PLAYLIST_POLL_INTERVAL_MS, STORAGE_KEYS } from "@/lib/constants";
import { MessageKey, useI18n } from "@/lib/i18n";

type ScreenInfo = { name: string; slug: string; description: string };

type QrOverlay = { position: string; message: string | null; image_url: string; share_url: string };

type PlaybackAsset = {
  id: string;
  kind: string;
  page_number: number | null;
  display_seconds: number | null;
  duration_seconds: number | null;
  url: string;
};

type PlaybackItem = {
  item_id: string;
  content_id: string;
  kind: string;
  title: string;
  duration_seconds: number;
  payload: Record<string, unknown>;
  assets: PlaybackAsset[];
  qr: QrOverlay | null;
};

type EmergencyPayload = {
  address?: string;
  description?: string;
  sections?: { label: string; text: string }[];
  latitude?: number | null;
  longitude?: number | null;
};

type EmergencyPane = { type: "photo" | "video" | "map"; url?: string; lat?: number; lng?: number; seconds: number };

function readCache<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function writeCache(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage unavailable (private mode, quota exceeded): keep working without a cache.
  }
}

async function fetchWithTimeout(input: string, init?: RequestInit, timeoutMs = 8000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

function sortedAssets(item: PlaybackItem, kind: string): PlaybackAsset[] {
  return item.assets.filter((asset) => asset.kind === kind).sort((a, b) => (a.page_number ?? 0) - (b.page_number ?? 0));
}

/** Seconds for each page: its own display_seconds when set, otherwise the item's time split
 * evenly among the pages, never below the configured minimum. */
function pageDurations(pages: PlaybackAsset[], totalSeconds: number, display: DisplaySettings): number[] {
  const fallback = Math.max(display.min_page_seconds, totalSeconds / Math.max(1, pages.length));
  return pages.map((page) => (page.display_seconds && page.display_seconds > 0 ? page.display_seconds : fallback));
}

function spreadsheetRows(item: PlaybackItem): string[][] {
  return (item.payload.table as { rows?: string[][] } | undefined)?.rows ?? [];
}

function emergencyPanes(item: PlaybackItem, display: DisplaySettings): EmergencyPane[] {
  const payload = item.payload as EmergencyPayload;
  const panes: EmergencyPane[] = sortedAssets(item, "PHOTO").map((photo) => ({ type: "photo", url: photo.url, seconds: display.emergency_pane_seconds }));
  const video = item.assets.find((asset) => asset.kind === "VIDEO");
  if (video) {
    // The video plays to the end: its real length plus one second, not the photo duration.
    panes.push({ type: "video", url: video.url, seconds: Math.max(display.emergency_pane_seconds, Math.ceil(video.duration_seconds ?? 0) + 1) });
  }
  if (display.show_emergency_map && payload.latitude != null && payload.longitude != null) {
    panes.push({ type: "map", lat: payload.latitude, lng: payload.longitude, seconds: display.emergency_pane_seconds });
  }
  return panes;
}

/** Minimum time an item needs to show all of its pages, table rows or emergency panes once.
 * The playlist never advances before that, whatever duration_seconds says. */
function minimumDisplaySeconds(item: PlaybackItem, display: DisplaySettings): number {
  const rows = spreadsheetRows(item);
  if (item.kind === "DOCUMENT" || item.kind === "PPTX" || (item.kind === "EXCEL" && rows.length === 0)) {
    const pages = sortedAssets(item, "PAGE");
    return pages.length > 1 ? pageDurations(pages, item.duration_seconds, display).reduce((sum, seconds) => sum + seconds, 0) : item.duration_seconds;
  }
  if (item.kind === "EXCEL") {
    const pageCount = Math.ceil(rows.length / display.spreadsheet_rows_per_page);
    return pageCount > 1 ? Math.max(display.min_page_seconds, item.duration_seconds / pageCount) * pageCount : item.duration_seconds;
  }
  if (item.kind === "EMERGENCY") {
    const panes = emergencyPanes(item, display);
    return panes.length > 1 ? panes.reduce((sum, pane) => sum + pane.seconds, 0) : item.duration_seconds;
  }
  return item.duration_seconds;
}

/** Rotate through N slots where each slot can last a different time (a page with its own
 * display_seconds, or a video that must play to the end). */
function useTimedRotation(durationsSeconds: number[]): number {
  const [index, setIndex] = useState(0);
  const durationsRef = useRef(durationsSeconds);
  durationsRef.current = durationsSeconds;
  const key = durationsSeconds.join(",");
  useEffect(() => {
    setIndex(0);
    if (durationsRef.current.length <= 1) return;
    let cancelled = false;
    let current = 0;
    let timer: ReturnType<typeof setTimeout>;
    const scheduleNext = () => {
      const seconds = durationsRef.current[current] > 0 ? durationsRef.current[current] : 4;
      timer = setTimeout(() => {
        if (cancelled) return;
        current = (current + 1) % durationsRef.current.length;
        setIndex(current);
        scheduleNext();
      }, seconds * 1000);
    };
    scheduleNext();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // `key` already captures the relevant durations; the rotation restarts only when they change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return index;
}

function Clock({ hour12 }: { hour12: boolean }) {
  const { locale, timeZone } = useI18n();
  // Rendered only after mounting: the server's time would not match the TV's first paint.
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  if (!now) return null;
  const format = (options: Intl.DateTimeFormatOptions) => {
    try {
      return new Intl.DateTimeFormat(locale, { timeZone, ...options }).format(now);
    } catch {
      return now.toLocaleString();
    }
  };
  return (
    <div className="board-clock">
      <Clock3 />
      <div>
        <strong>{format({ hour: "2-digit", minute: "2-digit", hour12 })}</strong>
        <span>{format({ weekday: "long", day: "numeric", month: "long" })}</span>
      </div>
    </div>
  );
}

function QrOverlayBadge({ qr }: { qr: QrOverlay }) {
  const { t } = useI18n();
  return (
    <div className={`board-qr board-qr-${qr.position}`}>
      <img src={qr.image_url} alt={t("board.qrAlt")} />
      {qr.message && <span>{qr.message}</span>}
    </div>
  );
}

function PlaceholderSlide({ title, text, onAir = false }: { title: string; text: string; onAir?: boolean }) {
  const { t } = useI18n();
  return (
    <div className="board-slide board-slide-placeholder">
      {onAir && <span className="board-live"><Radio size={17} /> {t("board.onAir")}</span>}
      <h1>{title}</h1>
      <p>{text}</p>
    </div>
  );
}

function PagedSlide({ item }: { item: PlaybackItem }) {
  const { t } = useI18n();
  const display = useDisplaySettings();
  const pages = sortedAssets(item, "PAGE");
  const pageIndex = useTimedRotation(pageDurations(pages, item.duration_seconds, display));
  if (pages.length === 0) return <PlaceholderSlide title={item.title} text={t("board.processingDocument")} onAir />;
  const current = pages[pageIndex % pages.length];
  return (
    <div className="board-slide board-slide-document">
      <img src={current.url} alt={item.title} />
      {pages.length > 1 && <span className="board-page-indicator">{pageIndex + 1} / {pages.length}</span>}
    </div>
  );
}

function ImageSlide({ item }: { item: PlaybackItem }) {
  const { t } = useI18n();
  const page = item.assets.find((asset) => asset.kind === "PAGE");
  if (!page) return <PlaceholderSlide title={item.title} text={t("board.processingImage")} />;
  return (
    <div className="board-slide board-slide-image">
      <img src={page.url} alt={item.title} />
    </div>
  );
}

function VideoSlide({ item }: { item: PlaybackItem }) {
  const { t } = useI18n();
  const video = item.assets.find((asset) => asset.kind === "VIDEO");
  if (!video) return <PlaceholderSlide title={item.title} text={t("board.processingVideo")} />;
  return (
    <div className="board-slide board-slide-video">
      <video key={video.id} src={video.url} autoPlay muted loop playsInline />
    </div>
  );
}

function SpreadsheetSlide({ item }: { item: PlaybackItem }) {
  const display = useDisplaySettings();
  const table = item.payload.table as { header?: string[]; rows?: string[][] } | undefined;
  const rows = table?.rows ?? [];
  const rowsPerPage = display.spreadsheet_rows_per_page;
  const pageCount = Math.max(1, Math.ceil(rows.length / rowsPerPage));
  const perPage = Math.max(display.min_page_seconds, item.duration_seconds / pageCount);
  const pageIndex = useTimedRotation(Array(pageCount).fill(perPage));
  // Without table data (e.g. charts or macros that could not be read) the printable PDF pages are shown.
  if (!table || rows.length === 0) return <PagedSlide item={item} />;
  const start = (pageIndex % pageCount) * rowsPerPage;
  const pageRows = rows.slice(start, start + rowsPerPage);
  return (
    <div className="board-slide board-slide-table">
      <h1>{item.title}</h1>
      <div className="board-table-wrap">
        <table>
          {table.header && table.header.some(Boolean) && (
            <thead><tr>{table.header.map((cell, index) => <th key={index}>{cell}</th>)}</tr></thead>
          )}
          <tbody>
            {pageRows.map((row, rowIndex) => (
              <tr key={start + rowIndex}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
      {pageCount > 1 && <span className="board-page-indicator">{pageIndex + 1} / {pageCount}</span>}
    </div>
  );
}

function EmergencySlide({ item }: { item: PlaybackItem }) {
  const { t } = useI18n();
  const display = useDisplaySettings();
  const payload = item.payload as EmergencyPayload;
  const panes = emergencyPanes(item, display);
  const paneIndex = useTimedRotation(panes.map((pane) => pane.seconds));
  const pane = panes[paneIndex % Math.max(1, panes.length)];

  return (
    <div className="board-slide board-emergency">
      <span className="board-live board-emergency-badge"><Radio size={17} /> {t("board.emergency")}</span>
      <h1>{item.title}</h1>
      {payload.address && <p className="board-emergency-address">{payload.address}</p>}
      <div className="board-emergency-body">
        <div className="board-emergency-text">
          {payload.description && <p>{payload.description}</p>}
          {payload.sections?.map((section, index) => (
            <div className="board-emergency-section" key={index}><strong>{section.label}</strong><span>{section.text}</span></div>
          ))}
        </div>
        {panes.length > 0 && (
          <div className="board-emergency-media">
            {pane?.type === "photo" && <img src={pane.url} alt={item.title} />}
            {pane?.type === "video" && <video key={pane.url} src={pane.url} autoPlay muted playsInline />}
            {pane?.type === "map" && (
              <iframe
                title={t("board.mapTitle")}
                src={`https://www.openstreetmap.org/export/embed.html?bbox=${(pane.lng ?? 0) - 0.01}%2C${(pane.lat ?? 0) - 0.01}%2C${(pane.lng ?? 0) + 0.01}%2C${(pane.lat ?? 0) + 0.01}&layer=mapnik&marker=${pane.lat}%2C${pane.lng}`}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/** Days of [start, end) as "YYYY-MM-DD". The values are already local dates, so the maths
 * is done in UTC to avoid the browser shifting them by its own time zone. */
function eachDay(start: string, end: string): string[] {
  const days: string[] = [];
  const cursor = new Date(`${start}T00:00:00Z`);
  while (cursor.toISOString().slice(0, 10) < end) {
    days.push(cursor.toISOString().slice(0, 10));
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return days;
}

/** Last day an event is visible on: the ICS end of an all-day entry is the next midnight. */
function lastDayOf(event: CalendarEvent): string {
  const end = event.end.slice(0, 10);
  if (!event.all_day || end <= event.start.slice(0, 10)) return end;
  const previous = new Date(`${end}T00:00:00Z`);
  previous.setUTCDate(previous.getUTCDate() - 1);
  return previous.toISOString().slice(0, 10);
}

/** Shared calendar (ICS). The backend downloads and expands the feed, so this only draws it
 * and keeps a copy: a TV without Internet access still shows the last known events. */
function CalendarSlide({ item }: { item: PlaybackItem }) {
  const { t, formatDateTime } = useI18n();
  const display = useDisplaySettings();
  const [feed, setFeed] = useState<CalendarFeed | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    setFeed(readCache<CalendarFeed>(STORAGE_KEYS.calendarCache(item.content_id)));
    async function load() {
      try {
        const response = await fetchWithTimeout(`${API_BASE}/public/calendar/${item.content_id}`);
        if (!response.ok) {
          if (active) setFailed(true);
          return;
        }
        const data: CalendarFeed = await response.json();
        if (!active) return;
        setFeed(data);
        setFailed(false);
        writeCache(STORAGE_KEYS.calendarCache(item.content_id), data);
      } catch {
        // Offline: the cached copy stays on screen until the next attempt.
      }
    }
    load();
    const timer = setInterval(load, CALENDAR_POLL_INTERVAL_MS);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [item.content_id]);

  if (!feed) {
    return <PlaceholderSlide title={item.title} text={t(failed ? "board.calendarUnavailable" : "board.calendarLoading")} onAir />;
  }

  // Local wall time formatted as UTC, so the clock shown is the one the calendar reported.
  const asUtc = (value: string) => `${value.length > 10 ? value : `${value}T00:00`}:00Z`;
  const dateLabel = (day: string, options: Intl.DateTimeFormatOptions) => formatDateTime(asUtc(day), { ...options, timeZone: "UTC" });
  const timeLabel = (event: CalendarEvent) =>
    event.all_day
      ? t("board.allDay")
      : formatDateTime(asUtc(event.start), { hour: "2-digit", minute: "2-digit", hour12: !display.clock_24h, timeZone: "UTC" });
  // "20:00 - 22:30", or the end date too when the event crosses midnight.
  const rangeLabel = (event: CalendarEvent) => {
    if (event.all_day) return t("board.allDay");
    const ends = formatDateTime(asUtc(event.end), { hour: "2-digit", minute: "2-digit", hour12: !display.clock_24h, timeZone: "UTC" });
    const sameDay = event.end.slice(0, 10) === event.start.slice(0, 10);
    return sameDay ? `${timeLabel(event)} – ${ends}` : `${timeLabel(event)} – ${dateLabel(event.end, { day: "numeric", month: "short" })} ${ends}`;
  };
  const eventsOn = (day: string) => feed.events.filter((event) => event.start.slice(0, 10) <= day && lastDayOf(event) >= day);
  const days = eachDay(feed.range_start, feed.range_end);
  // A week with a couple of events per day has room for times and places; a busy one does not.
  const busiestDay = days.reduce((most, day) => Math.max(most, eventsOn(day).length), 0);
  const density = busiestDay <= 2 ? "roomy" : busiestDay <= 4 ? "normal" : "tight";
  const perDay = feed.view === "month" ? 3 : density === "roomy" ? 4 : density === "normal" ? 6 : 10;
  const periodLabel =
    feed.view === "month"
      ? dateLabel(feed.period_start, { month: "long", year: "numeric" })
      : feed.view === "week"
        ? `${dateLabel(days[0], { day: "numeric", month: "short" })} – ${dateLabel(days[days.length - 1], { day: "numeric", month: "short" })}`
        : dateLabel(feed.period_start, { weekday: "long", day: "numeric", month: "long" });
  const today = new Date().toISOString().slice(0, 10);
  const dayEvents = feed.view === "day" ? eventsOn(feed.period_start) : [];

  return (
    <div className={`board-slide board-calendar board-calendar-${feed.view} density-${density}`}>
      <header className="board-calendar-head">
        <span className="board-live"><CalendarDays size={16} /> {item.title}</span>
        <h1>{periodLabel}</h1>
      </header>
      {feed.view === "day" && dayEvents.length === 1 ? (
        // A single event has the whole screen: times, place and description in full.
        <div className="board-calendar-single">
          <strong>{rangeLabel(dayEvents[0])}</strong>
          <h2>{dayEvents[0].title || t("board.noTitle")}</h2>
          {dayEvents[0].location && (
            <p className="board-calendar-where"><MapPin size={22} /> {dayEvents[0].location}</p>
          )}
          {dayEvents[0].description && <p className="board-calendar-description">{dayEvents[0].description}</p>}
        </div>
      ) : feed.view === "day" ? (
        <div className="board-calendar-list">
          {dayEvents.length === 0 && <p className="board-calendar-empty">{t("board.calendarEmpty")}</p>}
          {dayEvents.map((event, index) => (
            <div className="board-calendar-entry" key={`${event.uid}-${index}`}>
              <strong>{rangeLabel(event)}</strong>
              <div>
                <span>{event.title || t("board.noTitle")}</span>
                {event.location && <small>{event.location}</small>}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="board-calendar-grid">
          {[0, 1, 2, 3, 4, 5, 6].map((weekday) => (
            <span className="board-calendar-weekday" key={weekday}>{t(`day.short.${weekday}` as MessageKey)}</span>
          ))}
          {days.map((day) => {
            const events = eventsOn(day);
            const visible = events.slice(0, perDay);
            const outside = day < feed.period_start || day >= feed.period_end;
            return (
              <div className={`board-calendar-day${outside ? " outside" : ""}${day === today ? " today" : ""}`} key={day}>
                <span className="board-calendar-daynumber">{Number(day.slice(8, 10))}</span>
                {visible.map((event, index) => (
                  <span className="board-calendar-event" key={`${event.uid}-${index}`}>
                    {/* The month view only has room for the start time and the title. */}
                    <i>{feed.view === "week" && density === "roomy" ? rangeLabel(event) : timeLabel(event)}</i>{" "}
                    {event.title || t("board.noTitle")}
                    {feed.view === "week" && density !== "tight" && event.location && <em>{event.location}</em>}
                  </span>
                ))}
                {events.length > visible.length && (
                  <span className="board-calendar-more">{t("board.moreEvents", { count: events.length - visible.length })}</span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function SlideContent({ item }: { item: PlaybackItem }) {
  const { t } = useI18n();
  if (item.kind === "ANNOUNCEMENT") {
    const body = typeof item.payload.body === "string" ? item.payload.body : "";
    const background = typeof item.payload.background === "string" ? item.payload.background : "brand";
    return (
      <div className={`board-slide board-slide-announcement bg-${background}`}>
        <span className="board-live"><Radio size={17} /> {t("board.onAir")}</span>
        <h1>{item.title}</h1>
        <p>{body}</p>
      </div>
    );
  }
  if (item.kind === "IMAGE") return <ImageSlide item={item} />;
  if (item.kind === "VIDEO") return <VideoSlide item={item} />;
  if (item.kind === "DOCUMENT" || item.kind === "PPTX") return <PagedSlide item={item} />;
  if (item.kind === "EXCEL") return <SpreadsheetSlide item={item} />;
  if (item.kind === "EMERGENCY") return <EmergencySlide item={item} />;
  if (item.kind === "CALENDAR") return <CalendarSlide item={item} />;
  return <PlaceholderSlide title={item.title} text={t("board.unsupported", { kind: item.kind })} onAir />;
}

export default function BoardScreen({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const encodedSlug = encodeURIComponent(slug);
  const { t } = useI18n();
  const { branding, refreshBranding } = useBranding();
  const display = useDisplaySettings();
  const [screen, setScreen] = useState<ScreenInfo | null>(null);
  const [items, setItems] = useState<PlaybackItem[]>([]);
  const [connected, setConnected] = useState(true);
  const [missing, setMissing] = useState(false);
  const [slideIndex, setSlideIndex] = useState(0);
  const [emergency, setEmergency] = useState<PlaybackItem | null>(null);
  const itemsRef = useRef(items);
  itemsRef.current = items;

  async function loadScreen() {
    try {
      const response = await fetchWithTimeout(`${API_BASE}/public/screens/${encodedSlug}`);
      if (response.status === 404) {
        setMissing(true);
        return;
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const info: ScreenInfo = { name: data.name, slug: data.slug, description: data.description };
      setScreen(info);
      writeCache(STORAGE_KEYS.screenCache(slug), info);
      setMissing(false);
      setConnected(true);
    } catch {
      setConnected(false);
    }
  }

  async function loadPlaylist() {
    try {
      const response = await fetchWithTimeout(`${API_BASE}/public/screens/${encodedSlug}/playlist`);
      if (!response.ok) return;
      const data = await response.json();
      const nextItems: PlaybackItem[] = data.items ?? [];
      setItems((previous) => {
        const changed = previous.length !== nextItems.length || previous.some((item, index) => item.item_id !== nextItems[index]?.item_id);
        if (changed) setSlideIndex(0);
        return nextItems;
      });
      writeCache(STORAGE_KEYS.playlistCache(slug), nextItems);
    } catch {
      // Keep the cached playlist; the heartbeat already reports the lost connection.
    }
  }

  async function loadEmergency() {
    try {
      const response = await fetchWithTimeout(`${API_BASE}/public/active-emergency`);
      if (!response.ok) return;
      const data = await response.json();
      setEmergency(data.status === "ok" ? data.items[0] : null);
    } catch {
      // Offline: keep showing the last known emergency state until the next attempt.
    }
  }

  async function heartbeat() {
    try {
      const response = await fetchWithTimeout(`${API_BASE}/public/screens/${encodedSlug}/heartbeat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resolution: `${window.screen.width}x${window.screen.height}` }),
      });
      if (response.status === 404) {
        setMissing(true);
        return;
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setConnected(true);
      setMissing(false);
    } catch {
      setConnected(false);
    }
  }

  useEffect(() => {
    // Show the cached screen and playlist immediately, then refresh from the server.
    setScreen(readCache<ScreenInfo>(STORAGE_KEYS.screenCache(slug)));
    setItems(readCache<PlaybackItem[]>(STORAGE_KEYS.playlistCache(slug)) ?? []);
    loadScreen();
    loadPlaylist();
    loadEmergency();
    heartbeat();
    const heartbeatTimer = setInterval(heartbeat, HEARTBEAT_INTERVAL_MS);
    const playlistTimer = setInterval(loadPlaylist, PLAYLIST_POLL_INTERVAL_MS);
    const emergencyTimer = setInterval(loadEmergency, HEARTBEAT_INTERVAL_MS);
    return () => {
      clearInterval(heartbeatTimer);
      clearInterval(playlistTimer);
      clearInterval(emergencyTimer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      socket = new WebSocket(wsUrl(`/ws/screens/${encodedSlug}`));
      socket.onmessage = (event) => {
        try {
          if (JSON.parse(event.data)?.type === "branding_updated") refreshBranding();
        } catch {
          // Not JSON: treat it as a generic "something changed" signal.
        }
        loadPlaylist();
        loadEmergency();
      };
      socket.onclose = () => {
        retryTimer = setTimeout(connect, 5000);
      };
    }
    connect();
    return () => {
      if (retryTimer) clearTimeout(retryTimer);
      if (socket) {
        socket.onclose = null;
        socket.close();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  useEffect(() => {
    if (items.length === 0) return;
    const current = items[slideIndex % items.length];
    // Never move on before the item had time to show every page, slide or photo.
    const seconds = current ? Math.max(current.duration_seconds, minimumDisplaySeconds(current, display)) : display.default_item_seconds;
    const timer = setTimeout(() => setSlideIndex((index) => (index + 1) % itemsRef.current.length), Math.max(3, seconds) * 1000);
    return () => clearTimeout(timer);
  }, [slideIndex, items, display]);

  if (missing && !screen) {
    return (
      <main className="board-error">
        <Activity />
        <h1>{t("board.unavailableTitle")}</h1>
        <p>{t("board.unavailable")}</p>
      </main>
    );
  }

  const current = items.length > 0 ? items[slideIndex % items.length] : null;
  const footerText = branding?.board_footer_text || (screen ? `/screen/${screen.slug}` : t("board.preparing"));

  return (
    <main className="board-page">
      <header className="board-header">
        <BrandMark variant="board" />
        {display.show_clock && <Clock hour12={!display.clock_24h} />}
      </header>
      <section className={`board-stage ${emergency ? "board-stage-emergency" : ""}`}>
        <div className="ambient-ring ring-a" /><div className="ambient-ring ring-b" />
        {emergency ? (
          <EmergencySlide item={emergency} />
        ) : current ? (
          <>
            <SlideContent key={current.item_id} item={current} />
            {current.qr && <QrOverlayBadge qr={current.qr} />}
          </>
        ) : (
          <div className="board-placeholder">
            <span className="board-live"><Radio size={17} /> {t("board.activeScreen")}</span>
            <h1>{screen?.name ?? t("board.connecting")}</h1>
            <p>{screen?.description || t("board.ready")}</p>
            <div className="board-next"><Activity /><div><strong>{t("board.noContentTitle")}</strong><span>{t("board.noContent")}</span></div></div>
          </div>
        )}
      </section>
      <footer className="board-footer">
        <span>{footerText}</span>
        <span className={connected ? "connection-ok" : "connection-lost"}>
          {connected ? <><i /> {t("board.connected")}</> : <><WifiOff /> {t("board.reconnecting")}</>}
        </span>
      </footer>
    </main>
  );
}
