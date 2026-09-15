"use client";

import { use, useEffect, useState } from "react";
import { AlertTriangle, Download, FileText } from "lucide-react";

import PublicHeader from "@/components/PublicHeader";
import { API_BASE, PublicShareDetail } from "@/lib/api";
import { useBranding } from "@/lib/branding";
import { KIND_ICONS } from "@/lib/contentKinds";
import { useI18n } from "@/lib/i18n";

export default function SharePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const { t, language } = useI18n();
  const { branding } = useBranding();
  const [detail, setDetail] = useState<PublicShareDetail | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let active = true;
    // Labels such as "Photo 1" come from the backend, so they follow the chosen language.
    fetch(`${API_BASE}/public/share/${encodeURIComponent(token)}`, { headers: { "X-Language": language } })
      .then(async (response) => {
        if (!active) return;
        if (!response.ok) {
          setNotFound(true);
          return;
        }
        setDetail(await response.json());
      })
      .catch(() => {
        if (active) setNotFound(true);
      });
    return () => {
      active = false;
    };
  }, [token, language]);

  const footer = branding ? [branding.app_name, branding.organization_name].filter(Boolean).join(" · ") : "";

  if (notFound) {
    return (
      <main className="share-page">
        <PublicHeader />
        <div className="share-card">
          <AlertTriangle size={40} />
          <h1>{t("share.notFoundTitle")}</h1>
          <p>{t("share.notFound")}</p>
        </div>
      </main>
    );
  }

  if (!detail) {
    return (
      <main className="share-page">
        <PublicHeader />
        <div className="share-card"><span className="spinner" /> {t("common.loading")}</div>
      </main>
    );
  }

  const Icon = KIND_ICONS[detail.kind] ?? FileText;

  return (
    <main className="share-page">
      <PublicHeader />
      <div className="share-card">
        {detail.thumbnail_url ? <img className="share-thumb" src={detail.thumbnail_url} alt={detail.title} /> : <div className="share-icon"><Icon size={36} /></div>}
        <h1>{detail.title}</h1>
        {detail.items.length > 0 ? (
          <>
            <ul className="share-item-list">
              {detail.items.map((item) => (
                <li key={item.id} className="share-item-row">
                  <span>{item.label}</span>
                  <a href={item.url} download><Download size={16} /> {t("share.download")}</a>
                </li>
              ))}
            </ul>
            {detail.items.length > 1 && detail.download_url && (
              <a className="primary-button share-download" href={detail.download_url}><Download size={18} /> {t("share.downloadAll")}</a>
            )}
          </>
        ) : detail.downloadable && detail.download_url ? (
          <a className="primary-button share-download" href={detail.download_url}><Download size={18} /> {t("share.download")}</a>
        ) : (
          <p className="share-note">{t("share.noDownload")}</p>
        )}
      </div>
      {footer && <p className="share-footer">{footer}</p>}
    </main>
  );
}
