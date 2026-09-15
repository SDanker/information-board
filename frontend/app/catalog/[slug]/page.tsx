"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Archive, Monitor } from "lucide-react";

import PublicHeader from "@/components/PublicHeader";
import { API_BASE, LibraryItem } from "@/lib/api";
import { KIND_ICONS, tokenFromShareUrl } from "@/lib/contentKinds";
import { MessageKey, useI18n } from "@/lib/i18n";

type ScreenLibrary = { screen_name: string; items: LibraryItem[] };

/** The page a screen's QR code opens: every shareable item rotating on that screen. */
export default function CatalogPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const { t } = useI18n();
  const [data, setData] = useState<ScreenLibrary | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let active = true;
    fetch(`${API_BASE}/public/screens/${encodeURIComponent(slug)}/library`)
      .then(async (response) => {
        if (!active) return;
        if (!response.ok) {
          setNotFound(true);
          return;
        }
        setData(await response.json());
      })
      .catch(() => {
        if (active) setNotFound(true);
      });
    return () => {
      active = false;
    };
  }, [slug]);

  if (notFound) {
    return (
      <main className="library-page">
        <PublicHeader />
        <div className="library-header">
          <AlertTriangle />
          <h1>{t("catalog.notFoundTitle")}</h1>
          <p>{t("catalog.notFound")}</p>
        </div>
      </main>
    );
  }

  return (
    <main className="library-page">
      <PublicHeader />
      <div className="library-header">
        <Monitor />
        <h1>{data?.screen_name ?? t("common.loading")}</h1>
        <p>{t("catalog.subtitle")}</p>
      </div>
      {data?.items.length === 0 && <p className="library-status">{t("catalog.empty")}</p>}
      <div className="library-grid">
        {data?.items.map((item) => {
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
