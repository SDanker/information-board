"use client";

import { useEffect, useState } from "react";
import { CalendarClock, MonitorCheck, RefreshCw } from "lucide-react";

import AdminShell from "@/components/AdminShell";
import { apiFetch, Playlist, PlaylistItem, Screen } from "@/lib/api";
import { useAuthReady } from "@/lib/auth";
import { MessageKey, useI18n } from "@/lib/i18n";

const WEEK_DAYS = [0, 1, 2, 3, 4, 5, 6];

function appliesOnDay(item: PlaylistItem, day: number): boolean {
  return !item.days_of_week || item.days_of_week.length === 0 || item.days_of_week.includes(day);
}

function isAlwaysOn(item: PlaylistItem): boolean {
  return !item.start_date && !item.end_date && (!item.days_of_week || item.days_of_week.length === 0) && !item.start_time && !item.end_time;
}

export default function SchedulePage() {
  const ready = useAuthReady();
  const { t, tp, formatDateTime } = useI18n();
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [screens, setScreens] = useState<Screen[]>([]);
  const [error, setError] = useState("");
  const [todayIndex, setTodayIndex] = useState<number | null>(null);

  useEffect(() => {
    // Monday = 0, like the backend; computed on the client only to avoid a hydration mismatch.
    setTodayIndex((new Date().getDay() + 6) % 7);
  }, []);

  async function load() {
    try {
      const [playlistList, screenList] = await Promise.all([apiFetch<Playlist[]>("/playlists"), apiFetch<Screen[]>("/screens")]);
      setPlaylists(playlistList);
      setScreens(screenList);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("schedule.loadError"));
    }
  }

  useEffect(() => {
    if (ready) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  // Dates are calendar days without a time zone, so they are formatted in UTC to avoid shifting a day.
  const formatDate = (value: string) => formatDateTime(`${value}T00:00:00Z`, { dateStyle: "medium", timeZone: "UTC" });

  function timeRangeLabel(item: PlaylistItem): string {
    if (item.start_time && item.end_time) return `${item.start_time.slice(0, 5)} – ${item.end_time.slice(0, 5)}`;
    return t("schedule.allDay");
  }

  function dateRangeLabel(item: PlaylistItem): string | null {
    if (item.start_date && item.end_date) return t("schedule.dateRange", { start: formatDate(item.start_date), end: formatDate(item.end_date) });
    if (item.start_date) return t("schedule.fromDate", { date: formatDate(item.start_date) });
    if (item.end_date) return t("schedule.untilDate", { date: formatDate(item.end_date) });
    return null;
  }

  return (
    <AdminShell page="schedule" eyebrow={t("eyebrow.operation")}>
      <section className="welcome-row">
        <div><h2>{t("schedule.title")}</h2><p>{t("schedule.subtitle")}</p></div>
        <div className="actions">
          <button className="secondary-button" onClick={() => load()}><RefreshCw size={17} /> {t("common.refresh")}</button>
        </div>
      </section>
      {error && <div className="form-error">{error}</div>}

      <section className="schedule-screens">
        <h3><MonitorCheck size={18} /> {t("schedule.screens")}</h3>
        {screens.length === 0 && <div className="empty-state"><p>{t("schedule.noScreens")}</p></div>}
        <div className="schedule-screens-grid">
          {screens.map((screen) => {
            const playlist = playlists.find((candidate) => candidate.id === screen.playlist_id) ?? null;
            const scheduledCount = playlist?.items.filter((item) => item.scheduled_now).length ?? 0;
            return (
              <div key={screen.id} className="schedule-screen-card">
                <strong>{screen.name}</strong>
                <span>{playlist ? playlist.name : t("schedule.noPlaylistAssigned")}</span>
                {playlist && <small>{t("schedule.scheduledNow", { scheduled: scheduledCount, total: playlist.items.length })}</small>}
              </div>
            );
          })}
        </div>
      </section>

      <section className="schedule-playlists">
        <h3><CalendarClock size={18} /> {t("schedule.playlists")}</h3>
        {playlists.length === 0 && <div className="empty-state"><p>{t("schedule.noPlaylists")}</p></div>}
        {playlists.map((playlist) => {
          const alwaysItems = playlist.items.filter(isAlwaysOn);
          const restrictedItems = playlist.items.filter((item) => !isAlwaysOn(item));
          return (
            <div key={playlist.id} className="schedule-card">
              <div className="schedule-card-header">
                <h4>{playlist.name}</h4>
                <span>{tp("playlists.screens", playlist.screen_count)}</span>
              </div>
              {playlist.items.length === 0 && <p className="empty-hint">{t("schedule.emptyPlaylist")}</p>}
              {alwaysItems.length > 0 && (
                <div className="schedule-always">
                  <strong>{t("schedule.alwaysOn")}</strong>
                  <ul>
                    {alwaysItems.map((item) => (
                      <li key={item.id} className={item.scheduled_now ? "active" : ""}>
                        {item.content?.title ?? t("playlists.deletedContent")} · {item.duration_seconds}s{!item.is_active && ` · ${t("schedule.paused")}`}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {restrictedItems.length > 0 && (
                <div className="schedule-grid">
                  {WEEK_DAYS.map((day) => {
                    const dayItems = restrictedItems.filter((item) => appliesOnDay(item, day));
                    return (
                      <div key={day} className={`schedule-day ${day === todayIndex ? "today" : ""}`}>
                        <header>{t(`day.long.${day}` as MessageKey)}</header>
                        {dayItems.length === 0 && <span className="schedule-day-empty">—</span>}
                        {dayItems.map((item) => {
                          const dates = dateRangeLabel(item);
                          return (
                            <div key={item.id} className={`schedule-chip ${item.scheduled_now && day === todayIndex ? "active" : ""} ${!item.is_active ? "paused" : ""}`}>
                              <strong>{item.content?.title ?? t("playlists.deletedContent")}</strong>
                              <span>{timeRangeLabel(item)}</span>
                              {dates && <small>{dates}</small>}
                            </div>
                          );
                        })}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </section>
    </AdminShell>
  );
}
