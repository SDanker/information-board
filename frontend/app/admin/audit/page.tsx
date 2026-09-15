"use client";

import { useEffect, useState } from "react";
import { RefreshCw, ShieldCheck } from "lucide-react";

import AdminShell from "@/components/AdminShell";
import { apiFetch, AuditLogEntry } from "@/lib/api";
import { useAuthReady } from "@/lib/auth";
import { hasMessage, useI18n } from "@/lib/i18n";

export default function AuditPage() {
  const ready = useAuthReady();
  const { t, formatDateTime } = useI18n();
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      setLogs(await apiFetch<AuditLogEntry[]>("/audit-logs?limit=200"));
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("audit.loadError"));
    }
  }

  useEffect(() => {
    if (ready) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  // Unknown actions or entity types (e.g. added by a newer backend) are shown as stored.
  function label(prefix: "audit.action" | "audit.entity", value: string): string {
    const key = `${prefix}.${value}`;
    return hasMessage(key) ? t(key) : value;
  }

  return (
    <AdminShell page="audit" eyebrow={t("eyebrow.operation")}>
      <section className="welcome-row">
        <div><h2>{t("audit.title")}</h2><p>{t("audit.subtitle")}</p></div>
        <button className="secondary-button" onClick={load}><RefreshCw size={17} /> {t("common.refresh")}</button>
      </section>
      {error && <div className="form-error">{error}</div>}
      <section className="panel">
        <div className="audit-list">
          {logs.length === 0 && <div className="empty-state"><ShieldCheck /><p>{t("audit.empty")}</p></div>}
          {logs.map((entry) => (
            <div className="audit-row" key={entry.id}>
              <span className="audit-time">{formatDateTime(entry.created_at, { dateStyle: "short", timeStyle: "medium" })}</span>
              <span className="audit-user">{entry.username}</span>
              <span className="audit-action">{label("audit.action", entry.action)} <strong>{label("audit.entity", entry.entity_type)}</strong></span>
              {entry.detail && Object.keys(entry.detail).length > 0 && (
                <span className="audit-detail">{Object.entries(entry.detail).map(([key, value]) => `${key}: ${value}`).join(" · ")}</span>
              )}
            </div>
          ))}
        </div>
      </section>
    </AdminShell>
  );
}
