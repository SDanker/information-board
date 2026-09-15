import { AlertTriangle, FileText, Film, Image as ImageIcon, Presentation, Table } from "lucide-react";

import type { ContentKind } from "./api";

export const KIND_ICONS: Record<ContentKind, typeof FileText> = {
  ANNOUNCEMENT: FileText,
  IMAGE: ImageIcon,
  VIDEO: Film,
  DOCUMENT: FileText,
  EXCEL: Table,
  PPTX: Presentation,
  EMERGENCY: AlertTriangle,
};

/** The API returns absolute share URLs (PUBLIC_BASE_URL); keep only the token so links stay
 * relative to the origin the visitor is actually using. */
export function tokenFromShareUrl(shareUrl: string): string {
  return shareUrl.split("/share/")[1] ?? "";
}
