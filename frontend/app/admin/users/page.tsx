"use client";

import { FormEvent, useEffect, useState } from "react";
import { Check, KeyRound, Plus, Power, RefreshCw, ShieldCheck, Trash2, UserPlus, X } from "lucide-react";

import AdminShell from "@/components/AdminShell";
import { apiFetch, AppUser } from "@/lib/api";
import { useAuthReady } from "@/lib/auth";
import { MessageKey, useI18n } from "@/lib/i18n";

const ROLES: AppUser["role"][] = ["ADMIN", "EDITOR", "OPERATOR"];

export default function UsersPage() {
  const ready = useAuthReady();
  const { t } = useI18n();
  const [users, setUsers] = useState<AppUser[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  function fail(reason: unknown, fallback: MessageKey) {
    setError(reason instanceof Error ? reason.message : t(fallback));
  }

  async function load() {
    try {
      setUsers(await apiFetch<AppUser[]>("/users"));
      setError("");
    } catch (reason) {
      fail(reason, "users.loadError");
    }
  }

  useEffect(() => {
    if (ready) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  async function createUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      await apiFetch("/users", {
        method: "POST",
        body: JSON.stringify({ username: data.get("username"), password: data.get("password"), role: data.get("role") }),
      });
      setMessage(t("users.created"));
      setShowForm(false);
      await load();
    } catch (reason) {
      fail(reason, "users.createError");
    } finally {
      setSaving(false);
    }
  }

  async function changeRole(user: AppUser, role: string) {
    try {
      await apiFetch(`/users/${user.id}`, { method: "PATCH", body: JSON.stringify({ role }) });
      await load();
    } catch (reason) {
      fail(reason, "users.roleError");
    }
  }

  async function toggleActive(user: AppUser) {
    try {
      await apiFetch(`/users/${user.id}`, { method: "PATCH", body: JSON.stringify({ is_active: !user.is_active }) });
      await load();
    } catch (reason) {
      fail(reason, "users.updateError");
    }
  }

  async function resetPassword(user: AppUser) {
    const password = window.prompt(t("users.passwordPrompt", { username: user.username }));
    if (!password) return;
    try {
      await apiFetch(`/users/${user.id}`, { method: "PATCH", body: JSON.stringify({ password }) });
      setMessage(t("users.passwordUpdated", { username: user.username }));
    } catch (reason) {
      fail(reason, "users.passwordError");
    }
  }

  async function remove(user: AppUser) {
    if (!window.confirm(t("users.deleteConfirm", { username: user.username }))) return;
    try {
      await apiFetch(`/users/${user.id}`, { method: "DELETE" });
      await load();
    } catch (reason) {
      fail(reason, "users.deleteError");
    }
  }

  return (
    <AdminShell page="users" eyebrow={t("eyebrow.operation")}>
      <section className="welcome-row">
        <div><h2>{t("users.title")}</h2><p>{t("users.subtitle")}</p></div>
        <div className="actions">
          <button className="secondary-button" onClick={load}><RefreshCw size={17} /> {t("common.refresh")}</button>
          <button className="primary-button" onClick={() => setShowForm(true)}><UserPlus size={18} /> {t("users.new")}</button>
        </div>
      </section>
      {message && <div className="success-message"><Check size={18} />{message}<button onClick={() => setMessage("")} aria-label={t("common.dismiss")}><X size={16} /></button></div>}
      {error && <div className="form-error">{error}</div>}

      <section className="panel">
        <div className="user-table">
          <div className="user-table-header">
            <span>{t("users.colUser")}</span><span>{t("users.colRole")}</span><span>{t("users.colStatus")}</span><span>{t("users.colActions")}</span>
          </div>
          {users.map((user) => (
            <div className="user-row" key={user.id}>
              <span className="user-name"><ShieldCheck size={16} /> {user.username}</span>
              <select value={user.role} onChange={(event) => changeRole(user, event.target.value)} aria-label={t("users.colRole")}>
                {ROLES.map((role) => <option key={role} value={role}>{t(`role.${role}`)}</option>)}
              </select>
              <span className={`status-badge ${user.is_active ? "online" : "offline"}`}><i />{t(user.is_active ? "common.active" : "common.inactive")}</span>
              <div className="user-actions">
                <button onClick={() => resetPassword(user)} aria-label={t("users.changePassword")} title={t("users.changePassword")}><KeyRound size={16} /></button>
                <button onClick={() => toggleActive(user)} className={user.is_active ? "danger-text" : "success-text"} aria-label={t("users.toggleActive")} title={t("users.toggleActive")}><Power size={16} /></button>
                <button onClick={() => remove(user)} className="danger-text" aria-label={t("users.delete")} title={t("users.delete")}><Trash2 size={16} /></button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {showForm && (
        <div className="modal-backdrop" role="presentation">
          <form className="modal-card" onSubmit={createUser}>
            <div className="modal-header">
              <div><span>{t("users.formEyebrow")}</span><h2>{t("users.formTitle")}</h2></div>
              <button type="button" onClick={() => setShowForm(false)} aria-label={t("common.close")}><X /></button>
            </div>
            <div className="form-grid">
              <label className="full">{t("users.username")}<input name="username" minLength={3} autoComplete="off" required /></label>
              <label className="full">{t("users.initialPassword")}<input name="password" type="password" minLength={8} autoComplete="new-password" required /></label>
              <label>
                {t("users.role")}
                <select name="role" defaultValue="OPERATOR">
                  {ROLES.map((role) => <option key={role} value={role}>{t(`role.${role}`)}</option>)}
                </select>
              </label>
            </div>
            <div className="modal-actions">
              <button type="button" className="secondary-button" onClick={() => setShowForm(false)}>{t("common.cancel")}</button>
              <button className="primary-button" disabled={saving}><Plus size={16} /> {saving ? t("users.creating") : t("users.create")}</button>
            </div>
          </form>
        </div>
      )}
    </AdminShell>
  );
}
