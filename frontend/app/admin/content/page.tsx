"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  AlertTriangle, Archive, CalendarClock, CalendarDays, Check, Clock3, Copy, FileText, Image as ImageIcon, Layers, MapPin, Megaphone,
  Pencil, Plus, RefreshCw, RotateCcw, RotateCw, Share2, ShieldOff, Trash2, X,
} from "lucide-react";

import AdminShell from "@/components/AdminShell";
import { API_BASE, apiFetch, CalendarConfig, CalendarView, Content, ContentKind, ShareInfo, uploadWithProgress } from "@/lib/api";
import { useAuthReady } from "@/lib/auth";
import { useBranding } from "@/lib/branding";
import { KIND_ICONS } from "@/lib/contentKinds";
import { MessageKey, useI18n } from "@/lib/i18n";
import {
  addDaysToInput, DEFAULT_PUBLICATION_DAYS, isArchivedContent, nowInputValue, PUBLICATION_PRESETS, publicationPeriodLabel, toggleWeekday, toInputValue, WEEK_DAYS,
} from "@/lib/publication";

const BACKGROUNDS = ["brand", "dark", "light"] as const;
const VISIBILITIES = ["LOCAL_PUBLIC", "QR_ONLY", "PRIVATE"] as const;
const CREATABLE_KINDS: ContentKind[] = ["ANNOUNCEMENT", "IMAGE", "VIDEO", "DOCUMENT", "EXCEL", "PPTX", "EMERGENCY", "CALENDAR"];
const CALENDAR_VIEWS: CalendarView[] = ["month", "week", "day"];
const UPLOAD_ACCEPT: Partial<Record<ContentKind, string>> = {
  IMAGE: ".jpg,.jpeg,.png,.webp,.bmp,.gif",
  VIDEO: ".mp4,.mov,.avi,.mkv,.webm",
  DOCUMENT: ".pdf,.doc,.docx,.odt,.txt,.rtf",
  EXCEL: ".xls,.xlsx,.csv",
  PPTX: ".ppt,.pptx,.odp",
};
const MEDIA_ACCEPT = `${UPLOAD_ACCEPT.IMAGE},${UPLOAD_ACCEPT.VIDEO}`;

type EmergencySection = { label: string; text: string };
type EmergencyPayload = {
  address?: string;
  description?: string;
  sections?: EmergencySection[];
  latitude?: number | null;
  longitude?: number | null;
};
type PageAsset = { id: string; page_number: number | null; display_seconds: number | null; url: string };

function mapEmbedUrl(lat: number, lng: number): string {
  const delta = 0.01;
  const bbox = [lng - delta, lat - delta, lng + delta, lat + delta].join("%2C");
  return `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat}%2C${lng}`;
}

function pagesOf(item: Content): PageAsset[] {
  return (item.published_version?.assets ?? [])
    .filter((asset) => asset.kind === "PAGE")
    .sort((a, b) => (a.page_number ?? 0) - (b.page_number ?? 0))
    .map((asset) => ({ id: asset.id, page_number: asset.page_number, display_seconds: asset.display_seconds, url: `${API_BASE}/public/assets/${asset.id}/file` }));
}

function countAssets(item: Content, kind: string): number {
  return item.published_version?.assets?.filter((asset) => asset.kind === kind).length ?? 0;
}

function withoutKey<T>(record: Record<string, T>, key: string): Record<string, T> {
  const next = { ...record };
  delete next[key];
  return next;
}

function calendarConfigOf(item: Content): CalendarConfig {
  const payload = (item.published_version?.payload ?? {}) as Partial<CalendarConfig>;
  return { ics_url: payload.ics_url ?? "", view: payload.view ?? "month" };
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function StatusBadge({ content }: { content: Content }) {
  const { t } = useI18n();
  const version = content.latest_version;
  const status = version?.status ?? "PENDING";
  // Finished publications live in the Archived segment, whether the worker already moved them or not.
  if (content.is_archived || content.publication_status === "expired") {
    return <span className="status-badge offline"><Archive size={12} />{t("content.status.archived")}</span>;
  }
  if (status === "READY") {
    if (content.publication_status === "scheduled") return <span className="status-badge processing"><Clock3 size={12} />{t("content.status.scheduled")}</span>;
    if (content.publication_status === "off_day") return <span className="status-badge processing"><Clock3 size={12} />{t("content.status.offDay")}</span>;
    return <span className="status-badge online"><i />{t("content.status.published")}{version ? ` · v${version.version_number}` : ""}</span>;
  }
  if (status === "FAILED") return <span className="status-badge offline"><AlertTriangle size={12} />{t("content.status.error")}</span>;
  return <span className="status-badge processing"><Clock3 size={12} />{t(status === "PROCESSING" ? "content.status.processing" : "content.status.queued")}</span>;
}

export default function ContentPage() {
  const ready = useAuthReady();
  const { t, tp, formatDateTime } = useI18n();
  const { branding } = useBranding();
  const [items, setItems] = useState<Content[]>([]);
  const [activeEmergencyId, setActiveEmergencyId] = useState<string | null>(null);
  const [editing, setEditing] = useState<Content | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [kind, setKind] = useState<ContentKind>("ANNOUNCEMENT");
  const [sections, setSections] = useState<EmergencySection[]>([{ label: "", text: "" }]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [sharing, setSharing] = useState<Content | null>(null);
  const [shareInfo, setShareInfo] = useState<ShareInfo | null>(null);
  const [shareBusy, setShareBusy] = useState(false);
  const [locating, setLocating] = useState<Content | null>(null);
  const [locateLat, setLocateLat] = useState("");
  const [locateLng, setLocateLng] = useState("");
  const [mediaFor, setMediaFor] = useState<Content | null>(null);
  // Upload progress per content id. It stays visible on the card after the modal closes,
  // because the upload keeps running in the background (XHR does not block the UI).
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});
  const [pagesFor, setPagesFor] = useState<Content | null>(null);
  const [pageDurations, setPageDurations] = useState<Record<string, string>>({});
  const [pagesSaving, setPagesSaving] = useState(false);
  // Publication period being edited in the form, as datetime-local values ("" = no limit).
  const [pubStart, setPubStart] = useState("");
  const [pubEnd, setPubEnd] = useState("");
  const [pubDays, setPubDays] = useState<number[]>([]);
  // Calendar publications: the ICS address and how the screens draw it.
  const [icsUrl, setIcsUrl] = useState("");
  const [calendarView, setCalendarView] = useState<CalendarView>("month");
  const [calendarTest, setCalendarTest] = useState("");
  const [calendarTesting, setCalendarTesting] = useState(false);
  // QR badge on the TV for this publication; calendars never show it.
  const [showQr, setShowQr] = useState(true);
  // Published = on screen or about to be; Archived = period ended (or archived by hand).
  const [segment, setSegment] = useState<"published" | "archived">("published");

  const kindLabel = (value: ContentKind) => t(`kind.${value}` as MessageKey);

  function fail(reason: unknown, fallback: MessageKey) {
    setError(reason instanceof Error ? reason.message : t(fallback));
  }

  async function load() {
    try {
      const [contentList, status] = await Promise.all([
        apiFetch<Content[]>("/content"),
        apiFetch<{ active: boolean; content_id: string | null }>("/emergencies/active-status"),
      ]);
      setItems(contentList);
      setActiveEmergencyId(status.active ? status.content_id : null);
      setError("");
    } catch (reason) {
      fail(reason, "content.loadError");
    }
  }

  useEffect(() => {
    if (ready) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  useEffect(() => {
    if (!ready) return;
    const processing = items.some((item) => ["PENDING", "PROCESSING"].includes(item.latest_version?.status ?? ""));
    if (!processing) return;
    const timer = setInterval(load, 4000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, items]);

  function openCreate() {
    setEditing(null);
    setKind("ANNOUNCEMENT");
    setSections([{ label: "", text: "" }]);
    // Pre-filled with the default period (now → now + default length) so it can be adjusted right away.
    const start = nowInputValue(branding?.timezone);
    const defaultDays = branding?.display.default_publication_days ?? DEFAULT_PUBLICATION_DAYS;
    setPubStart(start);
    setPubEnd(defaultDays > 0 ? addDaysToInput(start, defaultDays) : "");
    setPubDays([]);
    // The calendar of this installation, if Settings has one, so it is one click away.
    setIcsUrl(branding?.default_calendar_ics_url ?? "");
    setCalendarView("month");
    setCalendarTest("");
    setShowQr(true);
    setShowForm(true);
  }

  function openEdit(item: Content) {
    setEditing(item);
    setKind(item.kind);
    const eventSections = ((item.published_version?.payload ?? {}) as EmergencyPayload).sections;
    setSections(eventSections?.length ? eventSections : [{ label: "", text: "" }]);
    setPubStart(toInputValue(item.publish_start_at));
    setPubEnd(toInputValue(item.publish_end_at));
    setPubDays(item.publish_days ?? []);
    const calendar = item.kind === "CALENDAR" ? calendarConfigOf(item) : null;
    setIcsUrl(calendar?.ics_url ?? "");
    setCalendarView(calendar?.view ?? "month");
    setCalendarTest("");
    setShowQr((item.qr_overlay as { visible?: boolean } | null)?.visible !== false);
    setShowForm(true);
  }

  async function testCalendarLink() {
    setCalendarTesting(true);
    setCalendarTest("");
    try {
      const result = await apiFetch<{ total: number; upcoming: { title: string; start: string }[] }>(
        `/calendar/preview?url=${encodeURIComponent(icsUrl)}`,
      );
      const next = result.upcoming[0];
      setCalendarTest(
        next
          ? t("content.form.testOk", { count: result.total, title: next.title || t("content.noTitle"), date: next.start.replace("T", " ") })
          : t("content.form.testEmpty"),
      );
    } catch (reason) {
      setCalendarTest(reason instanceof Error ? reason.message : t("content.form.testFailed"));
    } finally {
      setCalendarTesting(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (pubStart && pubEnd && pubEnd <= pubStart) {
      setError(t("content.publication.endBeforeStart"));
      return;
    }
    setSaving(true);
    const data = new FormData(event.currentTarget);
    // Empty start = immediately, empty end = no end date, no weekday selected = every day.
    const publication = { publish_start_at: pubStart || null, publish_end_at: pubEnd || null, publish_days: pubDays.length ? pubDays : null };
    // null restores the default (the QR set in Settings); false hides it on this item only.
    const qrOverlay = showQr ? null : { visible: false };
    try {
      if (editing && kind === "EMERGENCY") {
        // Featured events keep their photos, video and broadcast state; only the texts change.
        await apiFetch(`/emergencies/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            title: data.get("title"),
            address: String(data.get("address") ?? ""),
            description: String(data.get("description") ?? ""),
            sections: sections.filter((section) => section.label.trim()),
            ...publication,
          }),
        });
        setMessage(t("content.updated"));
      } else if (editing) {
        await apiFetch(`/content/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify({ title: data.get("title"), library_visibility: data.get("visibility"), qr_overlay: qrOverlay, ...publication }),
        });
        if (kind === "ANNOUNCEMENT") {
          const announcement = { body: String(data.get("body") ?? ""), background: String(data.get("background") ?? "brand") };
          await apiFetch(`/content/${editing.id}/versions`, {
            method: "POST",
            body: JSON.stringify({ kind: "ANNOUNCEMENT", title: data.get("title"), announcement }),
          });
        }
        if (kind === "CALENDAR") {
          await apiFetch(`/content/${editing.id}/versions`, {
            method: "POST",
            body: JSON.stringify({ kind: "CALENDAR", title: data.get("title"), calendar: { ics_url: icsUrl, view: calendarView } }),
          });
        }
        setMessage(t("content.updated"));
      } else if (kind === "ANNOUNCEMENT") {
        const announcement = { body: String(data.get("body") ?? ""), background: String(data.get("background") ?? "brand") };
        await apiFetch("/content", {
          method: "POST",
          body: JSON.stringify({
            kind: "ANNOUNCEMENT",
            title: data.get("title"),
            library_visibility: data.get("visibility"),
            announcement,
            qr_overlay: qrOverlay,
            ...publication,
          }),
        });
        setMessage(t("content.created"));
      } else if (kind === "CALENDAR") {
        await apiFetch("/content", {
          method: "POST",
          body: JSON.stringify({
            kind: "CALENDAR",
            title: data.get("title"),
            library_visibility: data.get("visibility"),
            calendar: { ics_url: icsUrl, view: calendarView },
            qr_overlay: qrOverlay,
            ...publication,
          }),
        });
        setMessage(t("content.created"));
      } else if (kind === "EMERGENCY") {
        await apiFetch("/emergencies", {
          method: "POST",
          body: JSON.stringify({
            title: data.get("title"),
            address: data.get("address"),
            description: data.get("description"),
            sections: sections.filter((section) => section.label.trim()),
            ...publication,
          }),
        });
        setMessage(t("content.emergencyCreated"));
      } else {
        const file = data.get("file");
        if (!(file instanceof File) || file.size === 0) throw new Error(t("content.selectFile"));
        const upload = new FormData();
        upload.set("kind", kind);
        upload.set("title", String(data.get("title") ?? ""));
        upload.set("library_visibility", String(data.get("visibility") ?? "LOCAL_PUBLIC"));
        upload.set("publish_start_at", pubStart);
        upload.set("publish_end_at", pubEnd);
        upload.set("publish_days", pubDays.join(","));
        upload.set("file", file);
        const uploaded = await apiFetch<Content>("/content/upload", { method: "POST", body: upload });
        // The upload is multipart and carries no JSON fields, so the preference is set after it.
        if (!showQr) {
          await apiFetch(`/content/${uploaded.id}`, { method: "PATCH", body: JSON.stringify({ qr_overlay: qrOverlay }) });
        }
        setMessage(t("content.uploaded"));
      }
      setShowForm(false);
      await load();
    } catch (reason) {
      fail(reason, "content.saveError");
    } finally {
      setSaving(false);
    }
  }

  async function restore(item: Content) {
    try {
      await apiFetch(`/content/${item.id}/restore`, { method: "POST" });
      setMessage(t("content.restored"));
      await load();
    } catch (reason) {
      fail(reason, "content.restoreError");
    }
  }

  async function remove(item: Content) {
    if (!window.confirm(t("content.deleteConfirm", { title: item.title }))) return;
    try {
      await apiFetch(`/content/${item.id}`, { method: "DELETE" });
      await load();
    } catch (reason) {
      fail(reason, "content.deleteError");
    }
  }

  async function openShare(item: Content) {
    setSharing(item);
    setShareInfo(null);
    setShareBusy(true);
    try {
      setShareInfo(await apiFetch<ShareInfo>(`/content/${item.id}/share`));
    } catch (reason) {
      fail(reason, "content.shareError");
      setSharing(null);
    } finally {
      setShareBusy(false);
    }
  }

  async function rotateShare() {
    if (!sharing) return;
    setShareBusy(true);
    try {
      setShareInfo(await apiFetch<ShareInfo>(`/content/${sharing.id}/share/rotate`, { method: "POST" }));
    } catch (reason) {
      fail(reason, "content.rotateError");
    } finally {
      setShareBusy(false);
    }
  }

  async function copyShareLink() {
    if (!shareInfo) return;
    try {
      await navigator.clipboard.writeText(shareInfo.share_url);
      setMessage(t("content.linkCopied"));
    } catch {
      // Clipboard unavailable (insecure context): the link stays visible to copy by hand.
    }
  }

  async function retry(item: Content) {
    if (!item.latest_version) return;
    try {
      await apiFetch(`/content/${item.id}/versions/${item.latest_version.id}/retry`, { method: "POST" });
      await load();
    } catch (reason) {
      fail(reason, "content.retryError");
    }
  }

  function openLocation(item: Content) {
    const payload = (item.published_version?.payload ?? {}) as EmergencyPayload;
    setLocateLat(payload.latitude != null ? String(payload.latitude) : "");
    setLocateLng(payload.longitude != null ? String(payload.longitude) : "");
    setLocating(item);
  }

  async function submitLocation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!locating) return;
    try {
      await apiFetch(`/emergencies/${locating.id}/location`, {
        method: "PATCH",
        body: JSON.stringify({ latitude: Number(locateLat), longitude: Number(locateLng) }),
      });
      setMessage(t("content.locationUpdated"));
      setLocating(null);
      await load();
    } catch (reason) {
      fail(reason, "content.locationError");
    }
  }

  function submitMedia(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!mediaFor) return;
    const contentId = mediaFor.id;
    const files = Array.from((event.currentTarget.elements.namedItem("media") as HTMLInputElement).files ?? []);
    if (files.length === 0) {
      setError(t("content.selectMedia"));
      return;
    }

    // One file picker; files are sorted by type before sending because the API still
    // distinguishes photos (several) from the video (only one).
    const photos = files.filter((file) => file.type.startsWith("image/"));
    const videos = files.filter((file) => file.type.startsWith("video/"));
    if (videos.length > 1) setError(t("content.oneVideoOnly"));

    const formData = new FormData();
    photos.forEach((photo) => formData.append("photos", photo));
    if (videos[0]) formData.append("video", videos[0]);

    // The modal closes right away: the upload continues in the background and its progress
    // is shown on this emergency's card.
    setMediaFor(null);
    setUploadProgress((previous) => ({ ...previous, [contentId]: 0 }));

    uploadWithProgress(`/emergencies/${contentId}/media`, formData, (percent) => {
      setUploadProgress((previous) => ({ ...previous, [contentId]: percent }));
    })
      .then(() => {
        setMessage(t("content.mediaAdded"));
        load();
      })
      .catch((reason) => fail(reason, "content.mediaError"))
      .finally(() => setUploadProgress((previous) => withoutKey(previous, contentId)));
  }

  function openPages(item: Content) {
    const initial: Record<string, string> = {};
    pagesOf(item).forEach((page) => {
      initial[page.id] = page.display_seconds != null ? String(page.display_seconds) : "";
    });
    setPageDurations(initial);
    setPagesFor(item);
  }

  async function submitPages(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!pagesFor?.published_version) return;
    setPagesSaving(true);
    setError("");
    const versionId = pagesFor.published_version.id;
    try {
      await Promise.all(
        pagesOf(pagesFor).map((page) => {
          const raw = pageDurations[page.id] ?? "";
          const nextValue = raw.trim() === "" ? null : Number(raw);
          if (nextValue === page.display_seconds) return Promise.resolve();
          return apiFetch(`/content/${pagesFor.id}/versions/${versionId}/assets/${page.id}`, {
            method: "PATCH",
            body: JSON.stringify({ display_seconds: nextValue }),
          });
        }),
      );
      setMessage(t("content.pageDurationsSaved"));
      setPagesFor(null);
      await load();
    } catch (reason) {
      fail(reason, "content.pageDurationsError");
    } finally {
      setPagesSaving(false);
    }
  }

  async function broadcast(item: Content) {
    try {
      await apiFetch(`/emergencies/${item.id}/broadcast`, { method: "POST" });
      setMessage(t("content.broadcasting", { title: item.title }));
      await load();
    } catch (reason) {
      fail(reason, "content.broadcastError");
    }
  }

  async function clearBroadcast() {
    try {
      await apiFetch("/emergencies/clear-broadcast", { method: "POST" });
      setMessage(t("content.broadcastStopped"));
      await load();
    } catch (reason) {
      fail(reason, "content.stopError");
    }
  }

  const editingEvent = editing?.kind === "EMERGENCY" ? ((editing.published_version?.payload ?? {}) as EmergencyPayload) : null;
  const previewLat = Number(locateLat);
  const previewLng = Number(locateLng);
  const hasPreview = locateLat !== "" && locateLng !== "" && !Number.isNaN(previewLat) && !Number.isNaN(previewLng);
  const archivedItems = items.filter((item) => isArchivedContent(item, activeEmergencyId));
  const publishedItems = items.filter((item) => !isArchivedContent(item, activeEmergencyId));
  const visibleItems = segment === "archived" ? archivedItems : publishedItems;
  const submitLabel = saving
    ? t("common.saving")
    : editing
      ? t("common.saveChanges")
      : kind === "EMERGENCY"
        ? t("content.form.createEmergency")
        : kind === "CALENDAR"
          ? t("content.form.createCalendar")
          : kind === "ANNOUNCEMENT"
            ? t("content.form.create")
            : t("content.form.upload");

  return (
    <AdminShell page="content" eyebrow={t("eyebrow.content")}>
      <section className="welcome-row">
        <div><h2>{t("content.title")}</h2><p>{t("content.subtitle")}</p></div>
        <div className="actions">
          <button className="secondary-button" onClick={load}><RefreshCw size={17} /> {t("common.refresh")}</button>
          <button className="primary-button" onClick={openCreate}><Plus size={18} /> {t("content.new")}</button>
        </div>
      </section>
      {activeEmergencyId && (
        <div className="form-error emergency-banner">
          <AlertTriangle size={18} /> {t("content.emergencyLive")}
          <button className="secondary-button" onClick={clearBroadcast}><ShieldOff size={16} /> {t("content.stopBroadcast")}</button>
        </div>
      )}
      {message && <div className="success-message"><Check size={18} />{message}<button onClick={() => setMessage("")} aria-label={t("common.dismiss")}><X size={16} /></button></div>}
      {error && <div className="form-error">{error}</div>}
      <div className="settings-tabs" role="tablist">
        <button type="button" role="tab" aria-selected={segment === "published"} className={segment === "published" ? "active" : ""} onClick={() => setSegment("published")}>
          <FileText size={16} /> {t("content.tab.published")} <span className="tab-count">{publishedItems.length}</span>
        </button>
        <button type="button" role="tab" aria-selected={segment === "archived"} className={segment === "archived" ? "active" : ""} onClick={() => setSegment("archived")}>
          <Archive size={16} /> {t("content.tab.archived")} <span className="tab-count">{archivedItems.length}</span>
        </button>
      </div>
      {segment === "archived" && <p className="segment-hint">{t("content.archivedHint")}</p>}
      <section className="screen-cards">
        {visibleItems.length === 0 && (
          <div className="empty-state">{segment === "archived" ? <Archive /> : <FileText />}<p>{t(segment === "archived" ? "content.archivedEmpty" : "content.empty")}</p></div>
        )}
        {visibleItems.map((item) => {
          const archived = isArchivedContent(item, activeEmergencyId);
          const Icon = KIND_ICONS[item.kind];
          const failed = item.latest_version?.status === "FAILED";
          const isEmergency = item.kind === "EMERGENCY";
          const isActiveEmergency = isEmergency && activeEmergencyId === item.id;
          const emergencyPayload = isEmergency ? ((item.published_version?.payload ?? {}) as EmergencyPayload) : null;
          const pageCount = item.kind === "DOCUMENT" || item.kind === "PPTX" ? pagesOf(item).length : 0;
          const pageCountLabel = pageCount > 0 ? pageCount : failed ? "—" : t("content.processingShort");
          const description =
            item.kind === "ANNOUNCEMENT"
              ? (item.published_version?.payload.body as string | undefined) ?? t("content.noPublishedContent")
              : isEmergency
                ? emergencyPayload?.description || emergencyPayload?.address || t("content.noDescription")
                : item.kind === "CALENDAR"
                  ? t("content.calendarDescription")
                  : failed
                    ? item.latest_version?.error_message ?? t("content.processingFailed")
                    : t("content.uploadedFile");
          return (
            <article className={`screen-card ${isActiveEmergency ? "emergency-live" : ""}`} key={item.id}>
              <div className="screen-card-top">
                <div className="screen-preview active"><Icon size={20} /><span>{kindLabel(item.kind)}</span></div>
                {isActiveEmergency ? <span className="status-badge offline"><i />{t("content.status.live")}</span> : <StatusBadge content={item} />}
              </div>
              <h3>{item.title}</h3>
              <p>{description}</p>
              {isEmergency && (
                <dl>
                  <div><dt>{t("content.address")}</dt><dd>{emergencyPayload?.address || "—"}</dd></div>
                  <div>
                    <dt>{t("content.location")}</dt>
                    <dd>{emergencyPayload?.latitude != null ? `${emergencyPayload.latitude.toFixed(4)}, ${emergencyPayload.longitude?.toFixed(4)}` : t("content.notSet")}</dd>
                  </div>
                  <div><dt>{t("content.photos")}</dt><dd>{countAssets(item, "PHOTO")}</dd></div>
                  <div><dt>{t("content.videos")}</dt><dd>{countAssets(item, "VIDEO")}</dd></div>
                </dl>
              )}
              {item.kind === "PPTX" && <dl><div><dt>{t("content.slides")}</dt><dd>{pageCountLabel}</dd></div></dl>}
              {item.kind === "DOCUMENT" && <dl><div><dt>{t("content.pages")}</dt><dd>{pageCountLabel}</dd></div></dl>}
              {item.kind === "CALENDAR" && (
                <dl>
                  <div><dt>{t("content.form.calendarView")}</dt><dd>{t(`content.view.${calendarConfigOf(item).view}` as MessageKey)}</dd></div>
                  <div><dt>{t("content.calendarSource")}</dt><dd>{hostOf(calendarConfigOf(item).ics_url)}</dd></div>
                </dl>
              )}
              {(
                <dl>
                  <div><dt>{t("content.publication.period")}</dt><dd>{publicationPeriodLabel(item, { t, formatDateTime })}</dd></div>
                  {item.publish_days && item.publish_days.length > 0 && (
                    <div><dt>{t("content.publication.weekdaysShort")}</dt><dd>{item.publish_days.map((day) => t(`day.short.${day}` as MessageKey)).join(" · ")}</dd></div>
                  )}
                </dl>
              )}
              {uploadProgress[item.id] != null && (
                <div className="upload-progress">
                  <div className="upload-progress-bar"><span style={{ width: `${uploadProgress[item.id]}%` }} /></div>
                  <span className="upload-progress-label">{t("content.uploading", { percent: uploadProgress[item.id] })}</span>
                </div>
              )}
              <div className="screen-card-actions">
                {archived && (
                  <button onClick={() => restore(item)} className="success-text"><RotateCcw size={16} /> {t("content.restore")}</button>
                )}
                {!archived && <button onClick={() => openEdit(item)} className="success-text"><Pencil size={16} /> {t("common.edit")}</button>}
                {!archived && failed && <button onClick={() => retry(item)} className="success-text"><RotateCw size={16} /> {t("content.retry")}</button>}
                {!archived && pageCount > 1 && <button onClick={() => openPages(item)}><Layers size={16} /> {t("content.pagesAction")}</button>}
                {!archived && isEmergency && <button onClick={() => openLocation(item)}><MapPin size={16} /> {t("content.locationAction")}</button>}
                {!archived && isEmergency && <button onClick={() => setMediaFor(item)}><ImageIcon size={16} /> {t("content.media")}</button>}
                {!archived && isEmergency && (isActiveEmergency ? (
                  <button onClick={clearBroadcast} className="danger-text"><ShieldOff size={16} /> {t("content.stop")}</button>
                ) : (
                  <button onClick={() => broadcast(item)} className="success-text"><Megaphone size={16} /> {t("content.broadcast")}</button>
                ))}
                {item.library_visibility !== "PRIVATE" && item.kind !== "CALENDAR" && (
                  <button onClick={() => openShare(item)}><Share2 size={16} /> {t("content.share")}</button>
                )}
                <button onClick={() => remove(item)} className="danger-text"><Trash2 size={16} /> {t("common.delete")}</button>
              </div>
            </article>
          );
        })}
      </section>

      {showForm && (
        <div className="modal-backdrop" role="presentation">
          <form className="modal-card" onSubmit={submit}>
            <div className="modal-header">
              <div>
                <span>{t(editing ? "content.form.editEyebrow" : "content.form.newEyebrow")}</span>
                <h2>{t(editing ? "content.form.editTitle" : "content.form.createTitle")}</h2>
              </div>
              <button type="button" onClick={() => setShowForm(false)} aria-label={t("common.close")}><X /></button>
            </div>
            {!editing && (
              <div className="kind-picker">
                {CREATABLE_KINDS.map((value) => {
                  const KindIcon = KIND_ICONS[value];
                  return (
                    <button type="button" key={value} className={kind === value ? "active" : ""} onClick={() => setKind(value)}>
                      <KindIcon size={18} /><span>{kindLabel(value)}</span>
                    </button>
                  );
                })}
              </div>
            )}
            <div className="form-grid">
              <label className="full">{t("content.form.title")}<input name="title" defaultValue={editing?.title ?? ""} minLength={2} required /></label>
              {kind === "ANNOUNCEMENT" && (
                <>
                  <label className="full">
                    {t("content.form.message")}
                    <textarea name="body" defaultValue={(editing?.published_version?.payload.body as string) ?? ""} rows={4} required maxLength={4000} />
                  </label>
                  <label>
                    {t("content.form.background")}
                    <select name="background" defaultValue={(editing?.published_version?.payload.background as string) ?? "brand"}>
                      {BACKGROUNDS.map((value) => <option key={value} value={value}>{t(`content.background.${value}`)}</option>)}
                    </select>
                  </label>
                </>
              )}
              {kind === "EMERGENCY" && (
                <>
                  <label className="full">{t("content.form.address")}<input name="address" defaultValue={editingEvent?.address ?? ""} placeholder={t("content.form.addressPlaceholder")} /></label>
                  <label className="full">{t("content.form.description")}<textarea name="description" defaultValue={editingEvent?.description ?? ""} rows={3} maxLength={4000} /></label>
                </>
              )}
              {kind === "CALENDAR" && (
                <>
                  <label className="full">
                    {t("content.form.icsUrl")}
                    <input
                      name="ics_url"
                      type="url"
                      value={icsUrl}
                      onChange={(event) => setIcsUrl(event.target.value)}
                      placeholder="https://.../calendar.ics"
                      required
                    />
                    <small>{t("content.form.icsHint")}</small>
                  </label>
                  <label>
                    {t("content.form.calendarView")}
                    <select value={calendarView} onChange={(event) => setCalendarView(event.target.value as CalendarView)}>
                      {CALENDAR_VIEWS.map((view) => (
                        <option key={view} value={view}>{t(`content.view.${view}` as MessageKey)}</option>
                      ))}
                    </select>
                  </label>
                  <div className="full calendar-test">
                    <button type="button" className="secondary-button" onClick={testCalendarLink} disabled={calendarTesting || !icsUrl}>
                      <CalendarDays size={16} /> {calendarTesting ? t("content.form.testing") : t("content.form.testLink")}
                    </button>
                    {calendarTest && <span>{calendarTest}</span>}
                  </div>
                </>
              )}
              {UPLOAD_ACCEPT[kind] && !editing && (
                <label className="full">
                  {t("content.form.file")}
                  <input type="file" name="file" accept={UPLOAD_ACCEPT[kind]} required />
                  <small>{t("content.form.formats", { formats: UPLOAD_ACCEPT[kind]!.replaceAll(".", " ").trim() })}</small>
                </label>
              )}
              {kind !== "EMERGENCY" && (
                <label>
                  {t("content.form.visibility")}
                  <select name="visibility" defaultValue={editing?.library_visibility ?? "LOCAL_PUBLIC"}>
                    {VISIBILITIES.map((value) => <option key={value} value={value}>{t(`content.visibility.${value}`)}</option>)}
                  </select>
                </label>
              )}
              {kind !== "CALENDAR" && (
                <div className="full form-toggle">
                  <label>
                    <input type="checkbox" checked={showQr} onChange={(event) => setShowQr(event.target.checked)} />
                    {t("content.form.showQr")}
                  </label>
                  <small>{t("content.form.showQrHint")}</small>
                </div>
              )}
            </div>
            <fieldset className="publication-fields">
              <legend><CalendarClock size={15} /> {t("content.publication.title")}</legend>
              <div className="form-grid">
                <label>
                  {t("content.publication.start")}
                  <input type="datetime-local" value={pubStart} onChange={(event) => setPubStart(event.target.value)} />
                </label>
                <label>
                  {t("content.publication.end")}
                  <input type="datetime-local" value={pubEnd} min={pubStart || undefined} onChange={(event) => setPubEnd(event.target.value)} />
                </label>
              </div>
              <div className="publication-presets">
                {PUBLICATION_PRESETS.map((days) => (
                  <button
                    type="button"
                    key={days}
                    className={pubStart && pubEnd === addDaysToInput(pubStart, days) ? "active" : ""}
                    onClick={() => setPubEnd(addDaysToInput(pubStart || nowInputValue(branding?.timezone), days))}
                  >
                    {tp("content.publication.days", days)}
                  </button>
                ))}
                <button type="button" className={pubEnd ? "" : "active"} onClick={() => setPubEnd("")}>{t("content.publication.noEnd")}</button>
              </div>
              <span className="publication-label">{t("content.publication.weekdays")}</span>
              <div className="day-picker">
                {WEEK_DAYS.map((day) => (
                  <button
                    type="button"
                    key={day}
                    aria-pressed={pubDays.includes(day)}
                    className={pubDays.includes(day) ? "day-active" : ""}
                    onClick={() => setPubDays((previous) => toggleWeekday(previous, day))}
                  >
                    {t(`day.short.${day}` as MessageKey)}
                  </button>
                ))}
              </div>
              <small className="form-hint">{t("content.publication.hint")}</small>
              {kind === "EMERGENCY" && <small className="form-hint">{t("content.publication.broadcastNote")}</small>}
            </fieldset>
            {kind === "EMERGENCY" && (
              <div className="emergency-sections">
                <p className="nav-label">{t("content.form.sections")}</p>
                {sections.map((section, index) => (
                  <div className="emergency-section-row" key={index}>
                    <input
                      placeholder={t("content.form.sectionTitle")}
                      value={section.label}
                      onChange={(event) => setSections((previous) => previous.map((s, i) => (i === index ? { ...s, label: event.target.value } : s)))}
                    />
                    <input
                      placeholder={t("content.form.sectionDetail")}
                      value={section.text}
                      onChange={(event) => setSections((previous) => previous.map((s, i) => (i === index ? { ...s, text: event.target.value } : s)))}
                    />
                    <button type="button" onClick={() => setSections((previous) => previous.filter((_, i) => i !== index))} aria-label={t("content.form.removeSection")}>
                      <X size={15} />
                    </button>
                  </div>
                ))}
                <button type="button" className="secondary-button" onClick={() => setSections((previous) => [...previous, { label: "", text: "" }])}>
                  <Plus size={15} /> {t("content.form.addSection")}
                </button>
                {!editing && <small className="form-hint">{t("content.form.mediaHint")}</small>}
              </div>
            )}
            <div className="modal-actions">
              <button type="button" className="secondary-button" onClick={() => setShowForm(false)}>{t("common.cancel")}</button>
              <button className="primary-button" disabled={saving}>{submitLabel}</button>
            </div>
          </form>
        </div>
      )}

      {sharing && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal-card share-modal">
            <div className="modal-header">
              <div><span>{t("content.shareEyebrow")}</span><h2>{sharing.title}</h2></div>
              <button type="button" onClick={() => setSharing(null)} aria-label={t("common.close")}><X /></button>
            </div>
            {shareBusy && !shareInfo ? (
              <p><span className="spinner" /> {t("content.generatingLink")}</p>
            ) : shareInfo ? (
              <>
                <img className="share-modal-qr" src={shareInfo.qr_url} alt={t("content.qrAlt")} />
                <div className="share-modal-link">
                  <input readOnly value={shareInfo.share_url} onFocus={(event) => event.target.select()} />
                  <button type="button" onClick={copyShareLink} aria-label={t("content.copyLink")}><Copy size={16} /></button>
                </div>
                <p className="share-modal-meta">{tp("content.downloadCount", shareInfo.download_count)}</p>
                <div className="modal-actions">
                  <button type="button" className="secondary-button" onClick={rotateShare} disabled={shareBusy}>
                    <RotateCw size={16} /> {t("content.rotateLink")}
                  </button>
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}

      {locating && (
        <div className="modal-backdrop" role="presentation">
          <form className="modal-card" onSubmit={submitLocation}>
            <div className="modal-header">
              <div><span>{t("content.locationEyebrow")}</span><h2>{locating.title}</h2></div>
              <button type="button" onClick={() => setLocating(null)} aria-label={t("common.close")}><X /></button>
            </div>
            {hasPreview && <iframe className="emergency-map-preview" src={mapEmbedUrl(previewLat, previewLng)} title={t("content.mapPreview")} loading="lazy" />}
            <div className="form-grid">
              <label>{t("content.latitude")}<input value={locateLat} onChange={(event) => setLocateLat(event.target.value)} type="number" step="any" min={-90} max={90} required /></label>
              <label>{t("content.longitude")}<input value={locateLng} onChange={(event) => setLocateLng(event.target.value)} type="number" step="any" min={-180} max={180} required /></label>
            </div>
            <small>{t("content.mapHint")}</small>
            <div className="modal-actions">
              <button type="button" className="secondary-button" onClick={() => setLocating(null)}>{t("common.cancel")}</button>
              <button className="primary-button">{t("content.saveLocation")}</button>
            </div>
          </form>
        </div>
      )}

      {pagesFor && (
        <div className="modal-backdrop" role="presentation">
          <form className="modal-card" onSubmit={submitPages}>
            <div className="modal-header">
              <div><span>{t("content.pagesEyebrow")}</span><h2>{pagesFor.title}</h2></div>
              <button type="button" onClick={() => setPagesFor(null)} aria-label={t("common.close")}><X /></button>
            </div>
            <small>{t("content.pagesHint")}</small>
            <div className="page-duration-list">
              {pagesOf(pagesFor).map((page, index) => {
                const label = t(pagesFor.kind === "PPTX" ? "content.slide" : "content.page", { number: index + 1 });
                return (
                  <div className="page-duration-row" key={page.id}>
                    <img src={page.url} alt={label} />
                    <span>{label}</span>
                    <label>
                      <input
                        type="number"
                        min={2}
                        max={600}
                        placeholder={t("content.auto")}
                        value={pageDurations[page.id] ?? ""}
                        onChange={(event) => setPageDurations((previous) => ({ ...previous, [page.id]: event.target.value }))}
                      />
                      s
                    </label>
                  </div>
                );
              })}
            </div>
            <div className="modal-actions">
              <button type="button" className="secondary-button" onClick={() => setPagesFor(null)}>{t("common.cancel")}</button>
              <button className="primary-button" disabled={pagesSaving}>{pagesSaving ? t("common.saving") : t("content.saveDurations")}</button>
            </div>
          </form>
        </div>
      )}

      {mediaFor && (
        <div className="modal-backdrop" role="presentation">
          <form className="modal-card" onSubmit={submitMedia}>
            <div className="modal-header">
              <div><span>{t("content.mediaEyebrow")}</span><h2>{mediaFor.title}</h2></div>
              <button type="button" onClick={() => setMediaFor(null)} aria-label={t("common.close")}><X /></button>
            </div>
            <div className="form-grid">
              <label className="full">
                {t("content.mediaLabel")}
                <input type="file" name="media" accept={MEDIA_ACCEPT} multiple />
              </label>
            </div>
            <small>{t("content.mediaHelp")}</small>
            <div className="modal-actions">
              <button type="button" className="secondary-button" onClick={() => setMediaFor(null)}>{t("common.cancel")}</button>
              <button className="primary-button">{t("content.upload")}</button>
            </div>
          </form>
        </div>
      )}
    </AdminShell>
  );
}
