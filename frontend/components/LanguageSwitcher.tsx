"use client";

import { Languages } from "lucide-react";

import { useI18n } from "@/lib/i18n";
import { isLanguage, LANGUAGES } from "@/lib/i18n/core";

export default function LanguageSwitcher({ tone = "light" }: { tone?: "light" | "dark" }) {
  const { language, setLanguage, t } = useI18n();

  return (
    <label className={`language-switcher language-switcher-${tone}`}>
      <Languages size={15} aria-hidden />
      <select
        value={language}
        aria-label={t("common.language")}
        onChange={(event) => {
          if (isLanguage(event.target.value)) setLanguage(event.target.value);
        }}
      >
        {LANGUAGES.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
