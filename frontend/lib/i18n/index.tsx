"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { PageKey, useBranding } from "../branding";
import { STORAGE_KEYS } from "../constants";
import { detectBrowserLanguage, interpolate, isLanguage, Language, setActiveLanguage } from "./core";
import { MESSAGES, MessageKey, PluralKey } from "./messages";

export type { Language } from "./core";
export type { MessageKey, PluralKey } from "./messages";
export { hasMessage } from "./messages";

type TranslateVars = Record<string, string | number>;

type I18nContextValue = {
  language: Language;
  setLanguage: (language: Language) => void;
  t: (key: MessageKey, vars?: TranslateVars) => string;
  /** Picks "<base>.one" or "<base>.other" and fills {count}. */
  tp: (base: PluralKey, count: number, vars?: TranslateVars) => string;
  formatDateTime: (value: string | number | Date, options?: Intl.DateTimeFormatOptions) => string;
  locale: string;
  timeZone: string | undefined;
};

const I18nContext = createContext<I18nContextValue | null>(null);

function readStoredLanguage(): Language | null {
  try {
    const value = localStorage.getItem(STORAGE_KEYS.language);
    return isLanguage(value) ? value : null;
  } catch {
    return null;
  }
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const { branding } = useBranding();
  const [chosenLanguage, setChosenLanguage] = useState<Language | null>(null);
  const [browserLanguage, setBrowserLanguage] = useState<Language | null>(null);

  useEffect(() => {
    // Read browser-only state after hydration so the server and the first client render match.
    setChosenLanguage(readStoredLanguage());
    setBrowserLanguage(detectBrowserLanguage());
  }, []);

  // A person's explicit choice wins, then the organization's default, then the browser.
  const language: Language = chosenLanguage ?? branding?.default_language ?? browserLanguage ?? "en";
  // Updated during render (not in an effect) because child effects, which fetch data, run
  // before this provider's effects and must already send the right language.
  setActiveLanguage(language);

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  const setLanguage = useCallback((next: Language) => {
    try {
      localStorage.setItem(STORAGE_KEYS.language, next);
    } catch {
      // Storage unavailable: the choice lasts for this visit only.
    }
    setChosenLanguage(next);
  }, []);

  const value = useMemo<I18nContextValue>(() => {
    const catalog = MESSAGES[language];
    const lookup = (key: MessageKey, vars?: TranslateVars) => interpolate(catalog[key] ?? MESSAGES.en[key] ?? key, vars);
    // The organization's locale (e.g. es-CL) only applies to its own default language.
    const locale = branding && language === branding.default_language ? branding.date_locale : language === "es" ? "es-ES" : "en-US";
    const timeZone = branding?.timezone || undefined;
    return {
      language,
      setLanguage,
      locale,
      timeZone,
      t: lookup,
      tp: (base, count, vars) => lookup(`${base}.${count === 1 ? "one" : "other"}` as MessageKey, { count, ...vars }),
      formatDateTime: (input, options = { dateStyle: "short", timeStyle: "short" }) => {
        try {
          return new Intl.DateTimeFormat(locale, { timeZone, ...options }).format(new Date(input));
        } catch {
          return new Date(input).toLocaleString();
        }
      },
    };
  }, [language, setLanguage, branding]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext);
  if (!context) throw new Error("useI18n must be used inside I18nProvider");
  return context;
}

/** Visible name of a navigation page: the administrator's custom label or the translated default. */
export function usePageLabel(): (page: PageKey) => string {
  const { branding } = useBranding();
  const { t } = useI18n();
  return useCallback((page: PageKey) => branding?.page_labels?.[page] || t(`nav.${page}` as MessageKey), [branding, t]);
}
