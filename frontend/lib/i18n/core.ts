// Framework-independent i18n helpers, usable from React components and plain modules alike.

export type Language = "en" | "es";

export const LANGUAGES: { value: Language; label: string }[] = [
  { value: "en", label: "English" },
  { value: "es", label: "Español" },
];

/** Declare a message group. Spanish must provide exactly the same keys as English. */
export function defineMessages<T extends Record<string, string>>(en: T, es: { [K in keyof T]: string }) {
  return { en: en as { [K in keyof T]: string }, es };
}

export function isLanguage(value: unknown): value is Language {
  return value === "en" || value === "es";
}

export function detectBrowserLanguage(): Language | null {
  if (typeof navigator === "undefined") return null;
  for (const tag of navigator.languages ?? [navigator.language]) {
    const primary = tag?.slice(0, 2).toLowerCase();
    if (isLanguage(primary)) return primary;
  }
  return null;
}

export function interpolate(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) => (name in vars ? String(vars[name]) : match));
}

// Mirror of the active language for code outside React, such as the API client, which
// sends it to the backend so error messages come back in the same language.
let activeLanguage: Language = "en";

export function setActiveLanguage(language: Language): void {
  activeLanguage = language;
}

export function getActiveLanguage(): Language {
  return activeLanguage;
}
