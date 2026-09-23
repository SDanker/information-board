"use client";

import { MessageKey, useI18n } from "@/lib/i18n";

export type LibraryTab = "current" | "archived";

/** Segments of the download pages: what is available now, and the archive of finished publications. */
export default function LibraryTabs({ value, onChange, currentLabel }: { value: LibraryTab; onChange: (tab: LibraryTab) => void; currentLabel: MessageKey }) {
  const { t } = useI18n();
  return (
    <div className="library-tabs" role="tablist">
      <button type="button" role="tab" aria-selected={value === "current"} className={value === "current" ? "active" : ""} onClick={() => onChange("current")}>
        {t(currentLabel)}
      </button>
      <button type="button" role="tab" aria-selected={value === "archived"} className={value === "archived" ? "active" : ""} onClick={() => onChange("archived")}>
        {t("library.tab.archived")}
      </button>
    </div>
  );
}
