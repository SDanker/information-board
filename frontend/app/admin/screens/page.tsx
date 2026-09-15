"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Check, Monitor, Plus, Power, RefreshCw, X } from "lucide-react";

import AdminShell from "@/components/AdminShell";
import { apiFetch, Playlist, Screen } from "@/lib/api";
import { useAuthReady } from "@/lib/auth";
import { MessageKey, useI18n } from "@/lib/i18n";

const RESOLUTIONS = ["1920x1080", "1366x768", "3840x2160", "1080x1920"];

export default function ScreensPage() {
  const ready = useAuthReady();
  const { t } = useI18n();
  const [screens, setScreens] = useState<Screen[]>([]);
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [slugPreview, setSlugPreview] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  function fail(reason: unknown, fallback: MessageKey) {
    setError(reason instanceof Error ? reason.message : t(fallback));
  }

  async function load() {
    try {
      const [screenList, playlistList] = await Promise.all([apiFetch<Screen[]>("/screens"), apiFetch<Playlist[]>("/playlists")]);
      setScreens(screenList);
      setPlaylists(playlistList);
      setError("");
    } catch (reason) {
      fail(reason, "screens.loadError");
    }
  }

  useEffect(() => {
    if (ready) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      await apiFetch<Screen>("/screens", {
        method: "POST",
        body: JSON.stringify({
          name: data.get("name"),
          slug: data.get("slug"),
          description: data.get("description"),
          expected_resolution: data.get("resolution"),
          orientation: data.get("orientation"),
          is_active: true,
        }),
      });
      setMessage(t("screens.created"));
      setShowForm(false);
      await load();
    } catch (reason) {
      fail(reason, "screens.createError");
    } finally {
      setSaving(false);
    }
  }

  async function toggle(screen: Screen) {
    try {
      await apiFetch(`/screens/${screen.id}`, { method: "PATCH", body: JSON.stringify({ is_active: !screen.is_active }) });
      await load();
    } catch (reason) {
      fail(reason, "screens.updateError");
    }
  }

  async function assignPlaylist(screen: Screen, playlistId: string) {
    try {
      await apiFetch(`/screens/${screen.id}`, { method: "PATCH", body: JSON.stringify({ playlist_id: playlistId || null }) });
      await load();
    } catch (reason) {
      fail(reason, "screens.assignError");
    }
  }

  return (
    <AdminShell page="screens" eyebrow={t("eyebrow.management")}>
      <section className="welcome-row">
        <div><h2>{t("screens.title")}</h2><p>{t("screens.subtitle")}</p></div>
        <div className="actions">
          <button className="secondary-button" onClick={load}><RefreshCw size={17} /> {t("common.refresh")}</button>
          <button className="primary-button" onClick={() => { setSlugPreview(""); setShowForm(true); }}><Plus size={18} /> {t("screens.new")}</button>
        </div>
      </section>
      {message && <div className="success-message"><Check size={18} />{message}<button onClick={() => setMessage("")} aria-label={t("common.dismiss")}><X size={16} /></button></div>}
      {error && <div className="form-error">{error}</div>}
      <section className="screen-cards">
        {screens.length === 0 && <div className="empty-state"><Monitor /><p>{t("screens.empty")}</p></div>}
        {screens.map((screen) => (
          <article className="screen-card" key={screen.id}>
            <div className="screen-card-top">
              <div className={`screen-preview ${screen.is_active ? "active" : "inactive"}`}><Monitor /><span>{screen.expected_resolution}</span></div>
              <span className={`status-badge ${screen.status.toLowerCase()}`}><i />{t(screen.status === "ONLINE" ? "common.online" : "common.offline")}</span>
            </div>
            <h3>{screen.name}</h3>
            <p>{screen.description || t("common.noDescription")}</p>
            <dl>
              <div><dt>{t("screens.route")}</dt><dd>/screen/{screen.slug}</dd></div>
              <div><dt>{t("screens.orientation")}</dt><dd>{t(screen.orientation === "landscape" ? "screens.landscape" : "screens.portrait")}</dd></div>
              <div><dt>{t("screens.lastIp")}</dt><dd>{screen.last_ip ?? "—"}</dd></div>
            </dl>
            <label className="playlist-select">
              {t("screens.assignedPlaylist")}
              <select value={screen.playlist_id ?? ""} onChange={(event) => assignPlaylist(screen, event.target.value)}>
                <option value="">{t("screens.noPlaylist")}</option>
                {playlists.map((playlist) => (
                  <option key={playlist.id} value={playlist.id}>{playlist.name} ({playlist.items.length})</option>
                ))}
              </select>
            </label>
            <div className="screen-card-actions">
              <Link href={`/screen/${screen.slug}`} target="_blank">{t("screens.open")} <ArrowUpRight size={16} /></Link>
              <button onClick={() => toggle(screen)} className={screen.is_active ? "danger-text" : "success-text"}>
                <Power size={16} />{t(screen.is_active ? "screens.deactivate" : "screens.activate")}
              </button>
            </div>
          </article>
        ))}
      </section>

      {showForm && (
        <div className="modal-backdrop" role="presentation">
          <form className="modal-card" onSubmit={create}>
            <div className="modal-header">
              <div><span>{t("screens.formEyebrow")}</span><h2>{t("screens.formTitle")}</h2></div>
              <button type="button" onClick={() => setShowForm(false)} aria-label={t("common.close")}><X /></button>
            </div>
            <div className="form-grid">
              <label>{t("screens.name")}<input name="name" placeholder={t("screens.namePlaceholder")} minLength={2} required /></label>
              <label>
                {t("screens.slug")}
                <input
                  name="slug"
                  placeholder={t("screens.slugPlaceholder")}
                  pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
                  minLength={2}
                  required
                  onChange={(event) => setSlugPreview(event.target.value)}
                />
                <small>{t("screens.slugHint", { slug: slugPreview || t("screens.slugPlaceholder") })}</small>
              </label>
              <label className="full">{t("screens.description")}<textarea name="description" placeholder={t("screens.descriptionPlaceholder")} /></label>
              <label>
                {t("screens.resolution")}
                <select name="resolution" defaultValue="1920x1080">
                  {RESOLUTIONS.map((resolution) => <option key={resolution}>{resolution}</option>)}
                </select>
              </label>
              <label>
                {t("screens.orientation")}
                <select name="orientation">
                  <option value="landscape">{t("screens.landscape")}</option>
                  <option value="portrait">{t("screens.portrait")}</option>
                </select>
              </label>
            </div>
            <div className="modal-actions">
              <button type="button" className="secondary-button" onClick={() => setShowForm(false)}>{t("common.cancel")}</button>
              <button className="primary-button" disabled={saving}>{saving ? t("common.saving") : t("screens.create")}</button>
            </div>
          </form>
        </div>
      )}
    </AdminShell>
  );
}
