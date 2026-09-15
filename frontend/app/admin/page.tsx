"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Activity, ArrowUpRight, Clock3, FileCheck2, MonitorCheck, MonitorX, Radio, RefreshCw, Server } from "lucide-react";

import AdminShell from "@/components/AdminShell";
import { apiFetch, Playlist, Screen, wsUrl } from "@/lib/api";
import { useAuthReady } from "@/lib/auth";
import { DASHBOARD_POLL_INTERVAL_MS, STORAGE_KEYS } from "@/lib/constants";
import { useI18n } from "@/lib/i18n";

export default function DashboardPage() {
  const ready = useAuthReady();
  const { t, tp, formatDateTime } = useI18n();
  const [screens, setScreens] = useState<Screen[]>([]);
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      const [screenList, playlistList] = await Promise.all([apiFetch<Screen[]>("/screens"), apiFetch<Playlist[]>("/playlists")]);
      setScreens(screenList);
      setPlaylists(playlistList);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("dashboard.loadError"));
    }
  }

  useEffect(() => {
    if (!ready) return;
    load();
    const timer = setInterval(load, DASHBOARD_POLL_INTERVAL_MS);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  useEffect(() => {
    if (!ready) return;
    const token = localStorage.getItem(STORAGE_KEYS.token);
    if (!token) return;
    const socket = new WebSocket(wsUrl(`/ws/admin?token=${encodeURIComponent(token)}`));
    socket.onmessage = () => load();
    return () => socket.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  const online = useMemo(() => screens.filter((screen) => screen.status === "ONLINE").length, [screens]);
  const itemCount = playlists.reduce((total, playlist) => total + playlist.items.length, 0);
  const scheduledCount = playlists.reduce((total, playlist) => total + playlist.items.filter((item) => item.scheduled_now).length, 0);

  return (
    <AdminShell page="dashboard" eyebrow={t("eyebrow.management")}>
      <section className="welcome-row">
        <div><h2>{t("dashboard.title")}</h2><p>{t("dashboard.subtitle")}</p></div>
        <button className="secondary-button" onClick={load}><RefreshCw size={17} /> {t("common.refresh")}</button>
      </section>
      {error && <div className="form-error">{error}</div>}
      <section className="metric-grid">
        <article className="metric-card accent-green">
          <div className="metric-icon"><MonitorCheck /></div>
          <div><span>{t("dashboard.screensOnline")}</span><strong>{online}<small> / {screens.length}</small></strong><p><i /> {t("dashboard.activeConnection")}</p></div>
        </article>
        <article className="metric-card accent-red">
          <div className="metric-icon"><MonitorX /></div>
          <div><span>{t("dashboard.screensOffline")}</span><strong>{screens.length - online}</strong><p>{t("dashboard.needsAttention")}</p></div>
        </article>
        <article className="metric-card accent-blue">
          <div className="metric-icon"><FileCheck2 /></div>
          <div><span>{t("dashboard.playlists")}</span><strong>{playlists.length}<small> / {tp("dashboard.items", itemCount)}</small></strong><p>{t("dashboard.rotationAssigned")}</p></div>
        </article>
        <article className="metric-card accent-amber">
          <div className="metric-icon"><Clock3 /></div>
          <div><span>{t("dashboard.scheduled")}</span><strong>{scheduledCount}</strong><p>{t("dashboard.scheduledHint")}</p></div>
        </article>
      </section>
      <section className="dashboard-grid">
        <article className="panel screens-panel">
          <div className="panel-header">
            <div><h3>{t("dashboard.screensPanel")}</h3><p>{t("dashboard.screensPanelHint")}</p></div>
            <Link href="/admin/screens">{t("dashboard.manage")} <ArrowUpRight size={16} /></Link>
          </div>
          <div className="screen-list">
            {screens.length === 0 ? (
              <div className="empty-state"><MonitorCheck /><p>{t("dashboard.noScreens")}</p></div>
            ) : (
              screens.map((screen) => (
                <div className="screen-row" key={screen.id}>
                  <div className={`screen-device ${screen.status.toLowerCase()}`}><MonitorCheck /></div>
                  <div className="screen-info"><strong>{screen.name}</strong><span>/{screen.slug} · {screen.expected_resolution}</span></div>
                  <span className={`status-badge ${screen.status.toLowerCase()}`}><i />{t(screen.status === "ONLINE" ? "common.online" : "common.offline")}</span>
                  <div className="last-seen">{screen.last_seen_at ? formatDateTime(screen.last_seen_at) : t("dashboard.noActivity")}</div>
                  <Link href={`/screen/${screen.slug}`} target="_blank" aria-label={t("dashboard.openScreen", { name: screen.name })}><ArrowUpRight /></Link>
                </div>
              ))
            )}
          </div>
        </article>
        <article className="panel activity-panel">
          <div className="panel-header"><div><h3>{t("dashboard.recentActivity")}</h3><p>{t("dashboard.systemEvents")}</p></div></div>
          <div className="timeline">
            <div><span className="timeline-icon green"><Server size={15} /></span><p><strong>{t("dashboard.servicesOk")}</strong><small>{t("dashboard.servicesOkHint")}</small></p></div>
            <div><span className="timeline-icon blue"><Radio size={15} /></span><p><strong>{t("dashboard.realtime")}</strong><small>{t("dashboard.realtimeHint")}</small></p></div>
            <div><span className="timeline-icon amber"><Activity size={15} /></span><p><strong>{tp("dashboard.playlistsConfigured", playlists.length)}</strong><small>{tp("dashboard.itemsInRotation", itemCount)}</small></p></div>
          </div>
        </article>
      </section>
    </AdminShell>
  );
}
