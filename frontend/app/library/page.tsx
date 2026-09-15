"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Archive } from "lucide-react";

import PublicHeader from "@/components/PublicHeader";
import { API_BASE, LibraryItem } from "@/lib/api";
import { useBranding } from "@/lib/branding";
import { KIND_ICONS, tokenFromShareUrl } from "@/lib/contentKinds";
import { MessageKey, useI18n } from "@/lib/i18n";

type LoadState = "loading" | "ready" | "disabled" | "error";

export default function LibraryPage() {
  const { t } = useI18n();
  const { branding } = useBranding();
  const [items, setItems] = useState<LibraryItem[]>([]);
  const [state, setState] = useState<LoadState>("loading");

  useEffect(() => {
    let active = true;
    fetch(`${API_BASE}/public/library`)
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

  const subtitle = branding?.organization_name
    ? t("library.subtitleOrganization", { organization: branding.organization_name })
    : t("library.subtitle");

  return (
    <main className="library-page">
      <PublicHeader />
      <div className="library-header">
        <Archive />
        <h1>{t("library.title")}</h1>
        <p>{subtitle}</p>
      </div>
      {state === "loading" && <p className="library-status">{t("common.loading")}</p>}
      {state === "disabled" && <p className="library-status">{t("library.disabled")}</p>}
      {state === "error" && <p className="library-status">{t("library.error")}</p>}
      {state === "ready" && items.length === 0 && <p className="library-status">{t("library.empty")}</p>}
      <div className="library-grid">
        {items.map((item) => {
          const Icon = KIND_ICONS[item.kind] ?? Archive;
          return (
            <Link key={item.id} href={`/share/${tokenFromShareUrl(item.share_url)}`} className="library-card">
              {item.thumbnail_url ? <img className="library-thumb" src={item.thumbnail_url} alt={item.title} /> : <div className="library-icon"><Icon size={28} /></div>}
              <strong>{item.title}</strong>
              <span>{t(`kind.${item.kind}` as MessageKey)}</span>
            </Link>
          );
        })}
      </div>
    </main>
  );
}
