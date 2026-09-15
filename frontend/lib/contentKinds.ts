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

/** The API returns absolute share URLs (the visitor's address, or PUBLIC_BASE_URL when it is
 * fixed); keep only the token so in-app links stay relative to the origin actually in use. */
export function tokenFromShareUrl(shareUrl: string): string {
  return shareUrl.split("/share/")[1] ?? "";
}
