"use client";

import { FormEvent, useEffect, useState } from "react";
import { Check, Clock3, GripVertical, ListPlus, PlaySquare, Plus, RefreshCw, Settings2, Trash2, X } from "lucide-react";

import AdminShell from "@/components/AdminShell";
import { apiFetch, Content, Playlist, PlaylistItem } from "@/lib/api";
import { isArchivedContent } from "@/lib/publication";
import { useAuthReady } from "@/lib/auth";
import { useDisplaySettings } from "@/lib/branding";
import { MessageKey, useI18n } from "@/lib/i18n";

const WEEK_DAYS = [0, 1, 2, 3, 4, 5, 6];

function toggleDay(days: number[] | null, day: number): number[] | null {
  const current = days ?? [];
  const next = current.includes(day) ? current.filter((value) => value !== day) : [...current, day].sort();
  return next.length === 0 ? null : next;
}

export default function PlaylistsPage() {
  const ready = useAuthReady();
  const { t, tp } = useI18n();
  const display = useDisplaySettings();
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [contents, setContents] = useState<Content[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [expandedItem, setExpandedItem] = useState<string | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);

  const selected = playlists.find((playlist) => playlist.id === selectedId) ?? null;

  function fail(reason: unknown, fallback: MessageKey) {
    setError(reason instanceof Error ? reason.message : t(fallback));
  }

  async function load(keepSelection = true) {
    try {
      const [playlistList, contentList] = await Promise.all([apiFetch<Playlist[]>("/playlists"), apiFetch<Content[]>("/content")]);
      setPlaylists(playlistList);
      setContents(contentList.filter((item) => !item.is_archived && item.published_version));
      if (!keepSelection || (selectedId && !playlistList.some((playlist) => playlist.id === selectedId))) {
        setSelectedId(playlistList[0]?.id ?? null);
      }
      setError("");
    } catch (reason) {
      fail(reason, "playlists.loadError");
    }
  }

  useEffect(() => {
    if (ready) load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  async function createPlaylist(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      const created = await apiFetch<Playlist>("/playlists", {
        method: "POST",
        body: JSON.stringify({ name: data.get("name"), description: data.get("description") }),
      });
      setShowCreate(false);
      setMessage(t("playlists.created"));
      await load();
      setSelectedId(created.id);
    } catch (reason) {
      fail(reason, "playlists.createError");
    }
  }

  async function deletePlaylist(playlist: Playlist) {
    if (!window.confirm(t("playlists.deleteConfirm", { name: playlist.name }))) return;
    try {
      await apiFetch(`/playlists/${playlist.id}`, { method: "DELETE" });
      await load(false);
    } catch (reason) {
      fail(reason, "playlists.deleteError");
    }
  }

  async function addItem(contentId: string) {
    if (!selected || !contentId) return;
    try {
      await apiFetch(`/playlists/${selected.id}/items`, {
        method: "POST",
        body: JSON.stringify({ content_id: contentId, duration_seconds: display.default_item_seconds }),
      });
      await load();
    } catch (reason) {
      fail(reason, "playlists.addError");
    }
  }

  async function patchItem(item: PlaylistItem, patch: Partial<PlaylistItem>) {
    if (!selected) return;
    try {
      await apiFetch(`/playlists/${selected.id}/items/${item.id}`, { method: "PATCH", body: JSON.stringify(patch) });
      await load();
    } catch (reason) {
      fail(reason, "playlists.updateError");
    }
  }

  async function removeItem(item: PlaylistItem) {
    if (!selected) return;
    try {
      await apiFetch(`/playlists/${selected.id}/items/${item.id}`, { method: "DELETE" });
      await load();
    } catch (reason) {
      fail(reason, "playlists.removeError");
    }
  }

  async function reorder(itemIds: string[]) {
    if (!selected) return;
    try {
      await apiFetch(`/playlists/${selected.id}/reorder`, { method: "POST", body: JSON.stringify({ item_ids: itemIds }) });
      await load();
    } catch (reason) {
      fail(reason, "playlists.reorderError");
    }
  }

  function onDrop(targetId: string) {
    if (!selected || !dragId || dragId === targetId) return;
    const ids = selected.items.map((item) => item.id);
    const from = ids.indexOf(dragId);
    const to = ids.indexOf(targetId);
    ids.splice(to, 0, ids.splice(from, 1)[0]);
    setDragId(null);
    reorder(ids);
  }

  return (
    <AdminShell page="playlists" eyebrow={t("eyebrow.content")}>
      <section className="welcome-row">
        <div><h2>{t("playlists.title")}</h2><p>{t("playlists.subtitle")}</p></div>
        <div className="actions">
          <button className="secondary-button" onClick={() => load()}><RefreshCw size={17} /> {t("common.refresh")}</button>
          <button className="primary-button" onClick={() => setShowCreate(true)}><Plus size={18} /> {t("playlists.new")}</button>
        </div>
      </section>
      {message && <div className="success-message"><Check size={18} />{message}<button onClick={() => setMessage("")} aria-label={t("common.dismiss")}><X size={16} /></button></div>}
      {error && <div className="form-error">{error}</div>}

      <section className="playlist-layout">
        <aside className="playlist-list">
          {playlists.length === 0 && <div className="empty-state"><PlaySquare /><p>{t("playlists.empty")}</p></div>}
          {playlists.map((playlist) => (
            <button
              key={playlist.id}
              className={`playlist-list-item ${playlist.id === selectedId ? "active" : ""}`}
              onClick={() => setSelectedId(playlist.id)}
            >
              <strong>{playlist.name}</strong>
              <span>{tp("playlists.items", playlist.items.length)} · {tp("playlists.screens", playlist.screen_count)}</span>
            </button>
          ))}
        </aside>

        <div className="playlist-detail">
          {!selected && <div className="empty-state"><PlaySquare /><p>{t("playlists.selectHint")}</p></div>}
          {selected && (
            <>
              <div className="panel-header">
                <div><h3>{selected.name}</h3><p>{selected.description || t("common.noDescription")}</p></div>
                <button className="danger-text" onClick={() => deletePlaylist(selected)}><Trash2 size={16} /> {t("playlists.delete")}</button>
              </div>

              <div className="playlist-add-row">
                <select
                  defaultValue=""
                  onChange={(event) => {
                    addItem(event.target.value);
                    event.target.value = "";
                  }}
                >
                  <option value="" disabled>{t("playlists.addContent")}</option>
                  {contents.filter((content) => !isArchivedContent(content)).map((content) => (
                    <option key={content.id} value={content.id}>{content.title}</option>
                  ))}
                </select>
                <ListPlus size={18} />
              </div>

              <ol className="playlist-items">
                {selected.items.map((item) => (
                  <li
                    key={item.id}
                    className={`playlist-item ${item.scheduled_now ? "" : "not-scheduled"}`}
                    draggable
                    onDragStart={() => setDragId(item.id)}
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={() => onDrop(item.id)}
                  >
                    <div className="playlist-item-row">
                      <GripVertical size={16} className="drag-handle" aria-label={t("playlists.dragHandle")} />
                      <div className="playlist-item-info">
                        <strong>{item.content?.title ?? t("playlists.deletedContent")}</strong>
                        <span>
                          {item.content ? t(`kind.${item.content.kind}` as MessageKey) : "—"}
                          {!item.scheduled_now && ` · ${t("playlists.outOfSchedule")}`}
                        </span>
                      </div>
                      <label className="duration-input">
                        <Clock3 size={14} />
                        <input
                          type="number"
                          min={3}
                          max={3600}
                          defaultValue={item.duration_seconds}
                          onBlur={(event) => {
                            const value = Number(event.target.value);
                            if (value !== item.duration_seconds) patchItem(item, { duration_seconds: value });
                          }}
                        />
                        s
                      </label>
                      <button type="button" className={item.is_active ? "success-text" : "danger-text"} onClick={() => patchItem(item, { is_active: !item.is_active })}>
                        {t(item.is_active ? "playlists.active" : "playlists.paused")}
                      </button>
                      <button type="button" onClick={() => setExpandedItem(expandedItem === item.id ? null : item.id)} aria-label={t("playlists.schedule")} title={t("playlists.schedule")}>
                        <Settings2 size={16} />
                      </button>
                      <button type="button" className="danger-text" onClick={() => removeItem(item)} aria-label={t("playlists.remove")} title={t("playlists.remove")}>
                        <X size={16} />
                      </button>
                    </div>
                    {expandedItem === item.id && (
                      <div className="playlist-item-schedule">
                        <label>{t("playlists.from")}<input type="date" defaultValue={item.start_date ?? ""} onChange={(event) => patchItem(item, { start_date: event.target.value || null })} /></label>
                        <label>{t("playlists.until")}<input type="date" defaultValue={item.end_date ?? ""} onChange={(event) => patchItem(item, { end_date: event.target.value || null })} /></label>
                        <label>{t("playlists.fromTime")}<input type="time" defaultValue={item.start_time ?? ""} onChange={(event) => patchItem(item, { start_time: event.target.value || null })} /></label>
                        <label>{t("playlists.untilTime")}<input type="time" defaultValue={item.end_time ?? ""} onChange={(event) => patchItem(item, { end_time: event.target.value || null })} /></label>
                        <div className="day-picker">
                          {WEEK_DAYS.map((day) => (
                            <button
                              type="button"
                              key={day}
                              className={item.days_of_week?.includes(day) ? "day-active" : ""}
                              onClick={() => patchItem(item, { days_of_week: toggleDay(item.days_of_week, day) })}
                            >
                              {t(`day.short.${day}` as MessageKey)}
                            </button>
                          ))}
                        </div>
                        <small>{t("playlists.everyDayHint")}</small>
                      </div>
                    )}
                  </li>
                ))}
                {selected.items.length === 0 && <div className="empty-state"><ListPlus /><p>{t("playlists.emptyItems")}</p></div>}
              </ol>
            </>
          )}
        </div>
      </section>

      {showCreate && (
        <div className="modal-backdrop" role="presentation">
          <form className="modal-card" onSubmit={createPlaylist}>
            <div className="modal-header">
              <div><span>{t("playlists.formEyebrow")}</span><h2>{t("playlists.formTitle")}</h2></div>
              <button type="button" onClick={() => setShowCreate(false)} aria-label={t("common.close")}><X /></button>
            </div>
            <div className="form-grid">
              <label className="full">{t("playlists.name")}<input name="name" placeholder={t("playlists.namePlaceholder")} minLength={2} required /></label>
              <label className="full">{t("playlists.description")}<textarea name="description" placeholder={t("playlists.descriptionPlaceholder")} /></label>
            </div>
            <div className="modal-actions">
              <button type="button" className="secondary-button" onClick={() => setShowCreate(false)}>{t("common.cancel")}</button>
              <button className="primary-button">{t("playlists.create")}</button>
            </div>
          </form>
        </div>
      )}
    </AdminShell>
  );
}
