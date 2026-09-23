"use client";

import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import {
  Activity, CalendarClock, Check, Clock3, Database, Globe, HardDrive, ImagePlus, KeyRound, LayoutList,
  Monitor, Palette, QrCode, RefreshCw, RotateCcw, Server, Trash2, User, X,
} from "lucide-react";

import AdminShell from "@/components/AdminShell";
import { apiFetch, SystemStatus, uploadWithProgress } from "@/lib/api";
import { useAuthReady } from "@/lib/auth";
import { Branding, DisplaySettings, PAGE_KEYS, PageKey, QrPosition, useBranding } from "@/lib/branding";
import { STORAGE_KEYS } from "@/lib/constants";
import { MessageKey, useI18n } from "@/lib/i18n";
import { isLanguage, LANGUAGES } from "@/lib/i18n/core";

type Tab = "branding" | "pages" | "display" | "system" | "account";
type NumberSetting = "default_item_seconds" | "min_page_seconds" | "emergency_pane_seconds" | "spreadsheet_rows_per_page" | "default_publication_days";
type ToggleSetting = "show_clock" | "clock_24h" | "show_qr" | "show_emergency_map";

const TABS: { id: Tab; icon: typeof Palette; label: MessageKey }[] = [
  { id: "branding", icon: Palette, label: "settings.tab.branding" },
  { id: "pages", icon: LayoutList, label: "settings.tab.pages" },
  { id: "display", icon: Monitor, label: "settings.tab.display" },
  { id: "system", icon: Server, label: "settings.tab.system" },
  { id: "account", icon: User, label: "settings.tab.account" },
];
const EDITABLE_TABS: Tab[] = ["branding", "pages", "display"];
const QR_POSITIONS: QrPosition[] = ["bottom-right", "bottom-left", "top-right", "top-left"];
const LOGO_ACCEPT = ".png,.jpg,.jpeg,.webp,.gif";
const MAX_LOGO_MB = 5;

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes;
  let unitIndex = -1;
  do {
    value /= 1024;
    unitIndex += 1;
  } while (value >= 1024 && unitIndex < units.length - 1);
  return `${value.toFixed(1)} ${units[unitIndex]}`;
}

function listTimeZones(): string[] {
  const intl = Intl as unknown as { supportedValuesOf?: (key: string) => string[] };
  try {
    return intl.supportedValuesOf?.("timeZone") ?? [];
  } catch {
    return [];
  }
}

export default function SettingsPage() {
  const ready = useAuthReady();
  const { t } = useI18n();
  const { setBranding } = useBranding();
  const [tab, setTab] = useState<Tab>("branding");
  const [draft, setDraft] = useState<Branding | null>(null);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [timeZones, setTimeZones] = useState<string[]>([]);
  const [isAdmin, setIsAdmin] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  function fail(reason: unknown, fallback: MessageKey) {
    setMessage("");
    setError(reason instanceof Error ? reason.message : t(fallback));
  }

  function succeed(key: MessageKey) {
    setError("");
    setMessage(t(key));
  }

  async function load() {
    try {
      const [branding, systemStatus] = await Promise.all([apiFetch<Branding>("/public/branding"), apiFetch<SystemStatus>("/system/status")]);
      setBranding(branding);
      setDraft(branding);
      setStatus(systemStatus);
      setError("");
    } catch (reason) {
      fail(reason, "settings.loadError");
    }
  }

  useEffect(() => {
    setIsAdmin(localStorage.getItem(STORAGE_KEYS.role) === "ADMIN");
    setTimeZones(listTimeZones());
  }, []);

  useEffect(() => {
    if (ready) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  function update<K extends keyof Branding>(key: K, value: Branding[K]) {
    setDraft((current) => (current ? { ...current, [key]: value } : current));
  }

  function updateDisplay<K extends keyof DisplaySettings>(key: K, value: DisplaySettings[K]) {
    setDraft((current) => (current ? { ...current, display: { ...current.display, [key]: value } } : current));
  }

  function updatePageLabel(page: PageKey, value: string) {
    setDraft((current) => (current ? { ...current, page_labels: { ...current.page_labels, [page]: value } } : current));
  }

  async function saveBranding(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft) return;
    setSaving(true);
    try {
      const { logo_url: _logoUrl, ...payload } = draft;
      const saved = await apiFetch<Branding>("/branding", { method: "PUT", body: JSON.stringify(payload) });
      setBranding(saved);
      setDraft(saved);
      succeed("settings.saved");
    } catch (reason) {
      fail(reason, "settings.saveError");
    } finally {
      setSaving(false);
    }
  }

  async function resetBranding() {
    if (!window.confirm(t("settings.resetConfirm"))) return;
    try {
      const saved = await apiFetch<Branding>("/branding", { method: "DELETE" });
      setBranding(saved);
      setDraft(saved);
      succeed("settings.resetDone");
    } catch (reason) {
      fail(reason, "settings.saveError");
    }
  }

  function applyLogo(saved: Branding) {
    setBranding(saved);
    // Only the logo changed on the server; keep any unsaved edits in the form.
    setDraft((current) => (current ? { ...current, logo_url: saved.logo_url } : saved));
  }

  async function uploadLogo(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    try {
      applyLogo(await uploadWithProgress<Branding>("/branding/logo", formData, () => undefined));
      succeed("settings.logoUploaded");
    } catch (reason) {
      fail(reason, "settings.logoError");
    }
  }

  async function removeLogo() {
    try {
      applyLogo(await apiFetch<Branding>("/branding/logo", { method: "DELETE" }));
      succeed("settings.logoRemoved");
    } catch (reason) {
      fail(reason, "settings.logoError");
    }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    if (data.get("new_password") !== data.get("confirm_password")) {
      setMessage("");
      setError(t("settings.passwordsDontMatch"));
      return;
    }
    setSaving(true);
    try {
      await apiFetch(
        "/users/me/password",
        { method: "POST", body: JSON.stringify({ current_password: data.get("current_password"), new_password: data.get("new_password") }) },
        { redirectOnUnauthorized: false },
      );
      form.reset();
      succeed("settings.passwordUpdated");
    } catch (reason) {
      fail(reason, "settings.passwordError");
    } finally {
      setSaving(false);
    }
  }

  function numberField(key: NumberSetting, label: MessageKey, min: number, max: number) {
    if (!draft) return null;
    return (
      <label className="settings-field">
        {t(label)}
        <input type="number" min={min} max={max} required value={draft.display[key]} onChange={(event) => updateDisplay(key, Number(event.target.value))} />
      </label>
    );
  }

  function toggleField(key: ToggleSetting, label: MessageKey) {
    if (!draft) return null;
    return (
      <label className="settings-toggle">
        <input type="checkbox" checked={draft.display[key]} onChange={(event) => updateDisplay(key, event.target.checked)} />
        {t(label)}
      </label>
    );
  }

  const locked = !isAdmin;
  const saveActions = (
    <div className="settings-actions">
      <button type="button" className="secondary-button" onClick={resetBranding}><RotateCcw size={16} /> {t("settings.reset")}</button>
      <button className="primary-button" disabled={saving}>{saving ? t("common.saving") : t("common.saveChanges")}</button>
    </div>
  );

  return (
    <AdminShell page="settings" eyebrow={t("eyebrow.operation")}>
      <section className="welcome-row">
        <div><h2>{t("settings.title")}</h2><p>{t("settings.subtitle")}</p></div>
        <button className="secondary-button" onClick={load}><RefreshCw size={17} /> {t("common.refresh")}</button>
      </section>

      <div className="settings-tabs" role="tablist">
        {TABS.map(({ id, icon: Icon, label }) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>
            <Icon size={16} /> {t(label)}
          </button>
        ))}
      </div>

      {message && <div className="success-message"><Check size={18} />{message}<button onClick={() => setMessage("")} aria-label={t("common.dismiss")}><X size={16} /></button></div>}
      {error && <div className="form-error">{error}</div>}
      {locked && EDITABLE_TABS.includes(tab) && <div className="settings-notice">{t("settings.adminOnly")}</div>}

      {draft && tab === "branding" && (
        <form onSubmit={saveBranding}>
          <fieldset className="settings-fieldset" disabled={locked}>
            <div className="settings-grid">
              <section className="settings-card">
                <h3><Palette size={17} /> {t("settings.identity")}</h3>
                <label className="settings-field">
                  {t("settings.appName")}
                  <input value={draft.app_name} maxLength={60} required onChange={(event) => update("app_name", event.target.value)} />
                  <small>{t("settings.appNameHint")}</small>
                </label>
                <label className="settings-field">
                  {t("settings.organization")}
                  <input value={draft.organization_name} maxLength={120} onChange={(event) => update("organization_name", event.target.value)} />
                  <small>{t("settings.organizationHint")}</small>
                </label>
                <label className="settings-field">
                  {t("settings.primaryColor")}
                  <span className="settings-color">
                    <input type="color" value={draft.primary_color} aria-label={t("settings.primaryColor")} onChange={(event) => update("primary_color", event.target.value)} />
                    <input value={draft.primary_color} pattern="#[0-9a-fA-F]{6}" maxLength={7} onChange={(event) => update("primary_color", event.target.value)} />
                  </span>
                </label>
                <div className="settings-field">
                  {t("settings.logo")}
                  <div className="logo-editor">
                    <div className="logo-preview">{draft.logo_url ? <img src={draft.logo_url} alt="" /> : <Activity />}</div>
                    <div>
                      <div className="logo-editor-actions">
                        <label className="secondary-button file-button">
                          <ImagePlus size={16} /> {t("settings.uploadLogo")}
                          <input type="file" accept={LOGO_ACCEPT} onChange={uploadLogo} />
                        </label>
                        {draft.logo_url && <button type="button" className="secondary-button" onClick={removeLogo}><Trash2 size={16} /> {t("settings.removeLogo")}</button>}
                      </div>
                      <small>{!draft.logo_url && `${t("settings.noLogo")} `}{t("settings.logoHint", { limit: MAX_LOGO_MB })}</small>
                    </div>
                  </div>
                </div>
              </section>

              <section className="settings-card">
                <h3><Globe size={17} /> {t("settings.regional")}</h3>
                <label className="settings-field">
                  {t("settings.defaultLanguage")}
                  <select value={draft.default_language} onChange={(event) => { if (isLanguage(event.target.value)) update("default_language", event.target.value); }}>
                    {LANGUAGES.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                  <small>{t("settings.defaultLanguageHint")}</small>
                </label>
                <label className="settings-field">
                  {t("settings.dateLocale")}
                  <input value={draft.date_locale} maxLength={35} required onChange={(event) => update("date_locale", event.target.value)} />
                  <small>{t("settings.dateLocaleHint")}</small>
                </label>
                <label className="settings-field">
                  {t("settings.timezone")}
                  <input value={draft.timezone} list="timezone-options" required onChange={(event) => update("timezone", event.target.value)} />
                  <datalist id="timezone-options">{timeZones.map((zone) => <option key={zone} value={zone} />)}</datalist>
                  <small>{t("settings.timezoneHint")}</small>
                </label>
              </section>

              <section className="settings-card">
                <h3><KeyRound size={17} /> {t("settings.loginTexts")}</h3>
                <p>{t("settings.leaveEmptyDefault")}</p>
                <label className="settings-field">
                  {t("settings.loginHeadline")}
                  <textarea value={draft.login_headline} maxLength={120} rows={2} placeholder={t("login.headline")} onChange={(event) => update("login_headline", event.target.value)} />
                </label>
                <label className="settings-field">
                  {t("settings.loginMessage")}
                  <textarea value={draft.login_message} maxLength={300} rows={3} placeholder={t("login.message")} onChange={(event) => update("login_message", event.target.value)} />
                </label>
              </section>

              <section className="settings-card">
                <h3><Globe size={17} /> {t("settings.publicPages")}</h3>
                <label className="settings-toggle">
                  <input type="checkbox" checked={draft.public_library_enabled} onChange={(event) => update("public_library_enabled", event.target.checked)} />
                  {t("settings.libraryEnabled")}
                </label>
                <p className="settings-help">{t("settings.libraryHint")}</p>
              </section>
            </div>
            {saveActions}
          </fieldset>
        </form>
      )}

      {draft && tab === "pages" && (
        <form onSubmit={saveBranding}>
          <fieldset className="settings-fieldset" disabled={locked}>
            <section className="settings-card">
              <h3><LayoutList size={17} /> {t("settings.tab.pages")}</h3>
              <p>{t("settings.pagesHint")}</p>
              <div className="page-label-grid">
                {PAGE_KEYS.map((page) => {
                  const defaultLabel = t(`nav.${page}` as MessageKey);
                  return (
                    <label className="settings-field" key={page}>
                      {defaultLabel}
                      <input value={draft.page_labels[page] ?? ""} maxLength={40} placeholder={defaultLabel} onChange={(event) => updatePageLabel(page, event.target.value)} />
                    </label>
                  );
                })}
              </div>
            </section>
            {saveActions}
          </fieldset>
        </form>
      )}

      {draft && tab === "display" && (
        <form onSubmit={saveBranding}>
          <fieldset className="settings-fieldset" disabled={locked}>
            <div className="settings-grid">
              <section className="settings-card">
                <h3><Clock3 size={17} /> {t("settings.rotation")}</h3>
                {numberField("default_item_seconds", "settings.defaultItemSeconds", 3, 3600)}
                {numberField("min_page_seconds", "settings.minPageSeconds", 2, 120)}
                {numberField("emergency_pane_seconds", "settings.emergencyPaneSeconds", 3, 120)}
                {numberField("spreadsheet_rows_per_page", "settings.rowsPerPage", 5, 40)}
              </section>
              <section className="settings-card">
                <h3><CalendarClock size={17} /> {t("settings.publications")}</h3>
                {numberField("default_publication_days", "settings.defaultPublicationDays", 0, 3650)}
                <p className="settings-help">{t("settings.defaultPublicationDaysHint")}</p>
                <label className="settings-field">
                  {t("settings.defaultCalendarUrl")}
                  <input
                    value={draft.default_calendar_ics_url}
                    maxLength={1000}
                    placeholder="https://.../calendar.ics"
                    onChange={(event) => update("default_calendar_ics_url", event.target.value)}
                  />
                  <small>{t("settings.defaultCalendarUrlHint")}</small>
                </label>
              </section>
              <section className="settings-card">
                <h3><Monitor size={17} /> {t("settings.tvElements")}</h3>
                {toggleField("show_clock", "settings.showClock")}
                {toggleField("clock_24h", "settings.clock24h")}
                {toggleField("show_emergency_map", "settings.showEmergencyMap")}
                <label className="settings-field">
                  {t("settings.footerText")}
                  <input value={draft.board_footer_text} maxLength={120} onChange={(event) => update("board_footer_text", event.target.value)} />
                  <small>{t("settings.footerTextHint")}</small>
                </label>
              </section>
              <section className="settings-card">
                <h3><QrCode size={17} /> {t("settings.qr")}</h3>
                {toggleField("show_qr", "settings.showQr")}
                <label className="settings-field">
                  {t("settings.qrPosition")}
                  <select value={draft.display.qr_position} onChange={(event) => updateDisplay("qr_position", event.target.value as QrPosition)}>
                    {QR_POSITIONS.map((position) => <option key={position} value={position}>{t(`settings.qr.${position}`)}</option>)}
                  </select>
                </label>
                <label className="settings-field">
                  {t("settings.qrMessage")}
                  <input value={draft.display.qr_message} maxLength={80} onChange={(event) => updateDisplay("qr_message", event.target.value)} />
                </label>
              </section>
            </div>
            {saveActions}
          </fieldset>
        </form>
      )}

      {tab === "system" && status && (
        <>
          {status.public_base_url_is_loopback && <p className="settings-notice">{t("settings.loopbackWarning")}</p>}
          <section className="metric-grid">
            <article className="metric-card accent-blue">
              <div className="metric-icon"><Server /></div>
              <div><span>{t("settings.environment")}</span><strong className="metric-text">{status.app_env}</strong><p>{status.timezone} · {t("settings.version", { version: status.version })}</p></div>
            </article>
            <article className="metric-card accent-green">
              <div className="metric-icon"><Activity /></div>
              <div>
                <span>{t("settings.worker")}</span>
                <strong className="metric-text">{t(status.worker_healthy ? "settings.workerActive" : "settings.workerNoSignal")}</strong>
                <p>{status.worker_seconds_since_heartbeat != null ? t("settings.secondsAgo", { seconds: status.worker_seconds_since_heartbeat }) : t("settings.noData")}</p>
              </div>
            </article>
            <article className="metric-card accent-amber">
              <div className="metric-icon"><HardDrive /></div>
              <div>
                <span>{t("settings.storage")}</span>
                <strong className="metric-text">{status.storage_bytes != null ? formatBytes(status.storage_bytes) : t("settings.unknownSize")}</strong>
                <p>{t(status.storage.backend === "s3" ? "settings.storageS3" : "settings.storageLocal", { location: status.storage.location })}</p>
              </div>
            </article>
            <article className="metric-card accent-red">
              <div className="metric-icon"><Globe /></div>
              <div>
                <span>{t("settings.publicAddress")}</span>
                <strong className="metric-text">{status.public_base_url}</strong>
                <p>
                  {t(status.public_base_url_mode === "auto" ? "settings.addressAuto" : "settings.addressFixed")}
                  {" · "}
                  {t("settings.adminNetworks", { networks: status.allowed_networks ?? t("settings.noRestriction") })}
                </p>
              </div>
            </article>
          </section>
          <section className="panel settings-counts">
            <h3><Database size={16} /> {t("settings.contentCounts")}</h3>
            <dl>
              <div><dt>{t("settings.countScreens")}</dt><dd>{status.counts.screens}</dd></div>
              <div><dt>{t("settings.countContents")}</dt><dd>{status.counts.contents}</dd></div>
              <div><dt>{t("settings.countPlaylists")}</dt><dd>{status.counts.playlists}</dd></div>
            </dl>
            <p>{t("settings.envHint")}</p>
          </section>
        </>
      )}

      {tab === "account" && (
        <section className="settings-card settings-account">
          <form onSubmit={changePassword}>
            <h3><KeyRound size={17} /> {t("settings.changePassword")}</h3>
            <label className="settings-field">{t("settings.currentPassword")}<input name="current_password" type="password" autoComplete="current-password" required minLength={1} /></label>
            <label className="settings-field">{t("settings.newPassword")}<input name="new_password" type="password" autoComplete="new-password" required minLength={8} /></label>
            <label className="settings-field">{t("settings.repeatPassword")}<input name="confirm_password" type="password" autoComplete="new-password" required minLength={8} /></label>
            <div className="settings-actions">
              <button className="primary-button" disabled={saving}>{saving ? t("common.saving") : t("settings.updatePassword")}</button>
            </div>
          </form>
        </section>
      )}
    </AdminShell>
  );
}
