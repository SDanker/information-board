"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Archive, Download } from "lucide-react";

import { API_BASE, LibraryItem } from "@/lib/api";
import { KIND_ICONS, tokenFromShareUrl } from "@/lib/contentKinds";
import { MessageKey, useI18n } from "@/lib/i18n";

type LoadState = "loading" | "ready" | "disabled" | "error";

/** The "Archived" segment of the download pages: publications whose period ended, each one
 * downloadable, plus a single zip with all of them. */
export default function ArchivedLibrary() {
  const { t, formatDateTime } = useI18n();
  const [items, setItems] = useState<LibraryItem[]>([]);
  const [state, setState] = useState<LoadState>("loading");

  useEffect(() => {
    let active = true;
    fetch(`${API_BASE}/public/library/archived`)
      .then(async (response) => {
        if (!active) return;
        if (response.status === 404) {
          setState("disabled");
          return;
        }
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        setItems(await response.json());
        setState("ready");
      })
      .catch(() => {
        if (active) setState("error");
      });
    return () => {
      active = false;
    };
  }, []);

  // The period end is local wall time without a zone: formatting it as UTC shows it as entered.
  const endedOn = (value: string) => formatDateTime(`${value.slice(0, 16)}:00Z`, { dateStyle: "medium", timeZone: "UTC" });

  return (
    <>
      <p className="library-status">{t("library.archivedSubtitle")}</p>
      {state === "loading" && <p className="library-status">{t("common.loading")}</p>}
      {state === "disabled" && <p className="library-status">{t("library.disabled")}</p>}
      {state === "error" && <p className="library-status">{t("library.error")}</p>}
      {state === "ready" && items.length === 0 && <p className="library-status">{t("library.archivedEmpty")}</p>}
      {items.length > 0 && (
        <a className="primary-button library-download-all" href={`${API_BASE}/public/library/archived/download`}>
          <Download size={17} /> {t("library.downloadAll")}
        </a>
      )}
      <div className="library-grid">
        {items.map((item) => {
          const Icon = KIND_ICONS[item.kind] ?? Archive;
          return (
            <Link key={item.id} href={`/share/${tokenFromShareUrl(item.share_url)}`} className="library-card">
              {item.thumbnail_url ? <img className="library-thumb" src={item.thumbnail_url} alt={item.title} /> : <div className="library-icon"><Icon size={28} /></div>}
              <strong>{item.title}</strong>
              <span>{t(`kind.${item.kind}` as MessageKey)}</span>
              {item.period_end && <em>{t("library.endedOn", { date: endedOn(item.period_end) })}</em>}
            </Link>
          );
        })}
      </div>
    </>
  );
}
