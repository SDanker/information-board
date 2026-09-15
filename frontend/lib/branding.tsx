"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { API_BASE } from "./api";
import { BRANDING_POLL_INTERVAL_MS, STORAGE_KEYS } from "./constants";
import type { Language } from "./i18n/core";

export const PAGE_KEYS = ["dashboard", "screens", "content", "playlists", "library", "schedule", "users", "audit", "settings"] as const;
export type PageKey = (typeof PAGE_KEYS)[number];
export type QrPosition = "bottom-right" | "bottom-left" | "top-right" | "top-left";

export type DisplaySettings = {
  default_item_seconds: number;
  min_page_seconds: number;
  emergency_pane_seconds: number;
  spreadsheet_rows_per_page: number;
  show_clock: boolean;
  clock_24h: boolean;
  show_qr: boolean;
  qr_position: QrPosition;
  qr_message: string;
  show_emergency_map: boolean;
};

export type Branding = {
  app_name: string;
  organization_name: string;
  primary_color: string;
  default_language: Language;
  date_locale: string;
  timezone: string;
  page_labels: Partial<Record<PageKey, string>>;
  login_headline: string;
  login_message: string;
  board_footer_text: string;
  public_library_enabled: boolean;
  display: DisplaySettings;
  logo_url: string | null;
};

// Values used until the server answers for the first time (same defaults as the backend).
export const DEFAULT_DISPLAY: DisplaySettings = {
  default_item_seconds: 15,
  min_page_seconds: 4,
  emergency_pane_seconds: 7,
  spreadsheet_rows_per_page: 14,
  show_clock: true,
  clock_24h: true,
  show_qr: true,
  qr_position: "bottom-right",
  qr_message: "",
  show_emergency_map: true,
};

type BrandingContextValue = {
  branding: Branding | null;
  refreshBranding: () => Promise<void>;
  setBranding: (branding: Branding) => void;
};

const BrandingContext = createContext<BrandingContextValue>({
  branding: null,
  refreshBranding: async () => {},
  setBranding: () => {},
});

function readCachedBranding(): Branding | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.branding);
    return raw ? (JSON.parse(raw) as Branding) : null;
  } catch {
    return null;
  }
}

export function BrandingProvider({ children }: { children: React.ReactNode }) {
  const [branding, setBrandingState] = useState<Branding | null>(null);

  const setBranding = useCallback((next: Branding) => {
    setBrandingState(next);
    try {
      localStorage.setItem(STORAGE_KEYS.branding, JSON.stringify(next));
    } catch {
      // Storage unavailable (private mode, quota): branding still applies for this visit.
    }
  }, []);

  const refreshBranding = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/public/branding`, { cache: "no-store" });
      if (response.ok) setBranding(await response.json());
    } catch {
      // Offline: keep the cached branding so screens keep their look without the server.
    }
  }, [setBranding]);

  useEffect(() => {
    // The cache avoids a flash of the default name/colors on every page load.
    const cached = readCachedBranding();
    if (cached) setBrandingState(cached);
    refreshBranding();
    const timer = setInterval(refreshBranding, BRANDING_POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [refreshBranding]);

  useEffect(() => {
    if (!branding) return;
    // --blue-600 drives buttons, links and highlights; lighter tints derive from it in globals.css.
    document.documentElement.style.setProperty("--blue-600", branding.primary_color);
    document.title = branding.organization_name ? `${branding.app_name} · ${branding.organization_name}` : branding.app_name;
    let icon = document.querySelector<HTMLLinkElement>("link[rel='icon']");
    if (branding.logo_url) {
      if (!icon) {
        icon = document.createElement("link");
        icon.rel = "icon";
        document.head.appendChild(icon);
      }
      icon.href = branding.logo_url;
    } else {
      icon?.remove();
    }
  }, [branding]);

  return <BrandingContext.Provider value={{ branding, refreshBranding, setBranding }}>{children}</BrandingContext.Provider>;
}

export function useBranding(): BrandingContextValue {
  return useContext(BrandingContext);
}

export function useDisplaySettings(): DisplaySettings {
  return useBranding().branding?.display ?? DEFAULT_DISPLAY;
}
