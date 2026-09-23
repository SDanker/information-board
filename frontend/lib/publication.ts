import type { Content, PublicationStatus } from "./api";
import type { MessageKey, useI18n } from "./i18n";

/*
 * Publication periods. The API keeps them as the installation's local wall time
 * ("YYYY-MM-DDTHH:MM:SS" without a zone), which is exactly what <input type="datetime-local">
 * edits, so values travel between the form and the API without time zone conversions.
 */

export const DEFAULT_PUBLICATION_DAYS = 7;

/** Archived by hand or by the worker, or already past its end (the worker archives those within a minute).
 * A featured event on the air stays where it is until its broadcast is stopped. */
export function isArchivedContent(item: Pick<Content, "id" | "is_archived" | "publication_status">, liveEventId?: string | null): boolean {
  if (item.is_archived) return true;
  return item.publication_status === "expired" && item.id !== liveEventId;
}
export const PUBLICATION_PRESETS = [1, 7, 14, 30];
export const WEEK_DAYS = [0, 1, 2, 3, 4, 5, 6];

export const PUBLICATION_STATUS_KEYS: Record<PublicationStatus, MessageKey> = {
  active: "content.status.published",
  scheduled: "content.status.scheduled",
  off_day: "content.status.offDay",
  expired: "content.status.expired",
};

// Sort order for lists: what is on screen first, what already ended last.
export const PUBLICATION_STATUS_ORDER: Record<PublicationStatus, number> = { active: 0, off_day: 1, scheduled: 2, expired: 3 };

/** Current minute in the given IANA time zone, formatted for a datetime-local input. */
export function nowInputValue(timeZone?: string): string {
  const format = (zone?: string) => {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: zone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).formatToParts(new Date());
    const part = (type: Intl.DateTimeFormatPartTypes) => parts.find((item) => item.type === type)?.value ?? "00";
    return `${part("year")}-${part("month")}-${part("day")}T${part("hour")}:${part("minute")}`;
  };
  try {
    return format(timeZone);
  } catch {
    // Unknown zone name: fall back to the browser's own time zone.
    return format(undefined);
  }
}

/** Calendar arithmetic on a wall-time value; UTC is used only so no daylight saving change interferes. */
export function addDaysToInput(value: string, days: number): string {
  const date = new Date(`${value.slice(0, 16)}:00Z`);
  if (Number.isNaN(date.getTime())) return "";
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 16);
}

export function toInputValue(value: string | null | undefined): string {
  return value ? value.slice(0, 16) : "";
}

export function toggleWeekday(days: number[], day: number): number[] {
  return days.includes(day) ? days.filter((item) => item !== day) : [...days, day].sort((a, b) => a - b);
}

type Formatting = Pick<ReturnType<typeof useI18n>, "t" | "formatDateTime">;

export function publicationPeriodLabel(item: Pick<Content, "publish_start_at" | "publish_end_at">, { t, formatDateTime }: Formatting): string {
  // Wall-time values carry no zone: formatting them as UTC shows the time exactly as entered.
  const format = (value: string) => formatDateTime(`${value.slice(0, 16)}:00Z`, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" });
  const { publish_start_at: start, publish_end_at: end } = item;
  if (start && end) return t("content.publication.range", { start: format(start), end: format(end) });
  if (end) return t("content.publication.until", { date: format(end) });
  if (start) return t("content.publication.from", { date: format(start) });
  return t("content.publication.always");
}
