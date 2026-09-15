import { STORAGE_KEYS } from "./constants";
import { getActiveLanguage } from "./i18n/core";
import { translate } from "./i18n/messages";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api/v1";

export type Screen = {
  id: string;
  name: string;
  slug: string;
  description: string;
  expected_resolution: string;
  orientation: "landscape" | "portrait";
  is_active: boolean;
  playlist_id: string | null;
  last_seen_at: string | null;
  last_ip: string | null;
  status: "ONLINE" | "OFFLINE";
};

export type ContentKind = "ANNOUNCEMENT" | "IMAGE" | "VIDEO" | "DOCUMENT" | "EXCEL" | "PPTX" | "EMERGENCY";

export type Asset = {
  id: string;
  kind: string;
  page_number: number | null;
  mime_type: string;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  display_seconds: number | null;
  size_bytes: number | null;
};

export type ContentVersion = {
  id: string;
  version_number: number;
  status: "PENDING" | "PROCESSING" | "READY" | "FAILED";
  payload: Record<string, unknown>;
  error_message: string | null;
  created_at: string;
  published_at: string | null;
  assets: Asset[];
};

export type Content = {
  id: string;
  kind: ContentKind;
  title: string;
  library_visibility: "LOCAL_PUBLIC" | "QR_ONLY" | "PRIVATE";
  qr_overlay: Record<string, unknown> | null;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  published_version: ContentVersion | null;
  latest_version: ContentVersion | null;
};

export type PlaylistItem = {
  id: string;
  content_id: string;
  order_index: number;
  duration_seconds: number;
  is_active: boolean;
  start_date: string | null;
  end_date: string | null;
  days_of_week: number[] | null;
  start_time: string | null;
  end_time: string | null;
  content: Content | null;
  scheduled_now: boolean;
};

export type Playlist = {
  id: string;
  name: string;
  description: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  items: PlaylistItem[];
  screen_count: number;
};

export type LibraryItem = {
  id: string;
  kind: ContentKind;
  title: string;
  thumbnail_url: string | null;
  share_url: string;
};

export type ShareInfo = {
  token: string;
  share_url: string;
  qr_url: string;
  download_url: string;
  revoked: boolean;
  download_count: number;
  created_at: string;
};

export type AppUser = {
  id: string;
  username: string;
  role: "ADMIN" | "EDITOR" | "OPERATOR";
  is_active: boolean;
  created_at: string;
};

export type AuditLogEntry = {
  id: string;
  username: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  detail: Record<string, unknown>;
  ip: string | null;
  created_at: string;
};

export type SystemStatus = {
  app_name: string;
  app_env: string;
  version: string;
  timezone: string;
  default_language: string;
  public_base_url: string;
  public_base_url_mode: "auto" | "fixed";
  public_base_url_is_loopback: boolean;
  allowed_networks: string | null;
  storage: { backend: "local" | "s3"; location: string; endpoint?: string };
  storage_bytes: number | null;
  worker_seconds_since_heartbeat: number | null;
  worker_healthy: boolean;
  counts: { screens: number; contents: number; playlists: number };
};

export type ShareDownloadItem = {
  id: string;
  kind: string;
  label: string;
  url: string;
};

export type PublicShareDetail = {
  title: string;
  kind: ContentKind;
  thumbnail_url: string | null;
  downloadable: boolean;
  download_url: string | null;
  items: ShareDownloadItem[];
};

function authToken(): string | null {
  return typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEYS.token) : null;
}

function buildHeaders(init?: RequestInit): Headers {
  const headers = new Headers(init?.headers);
  const token = authToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  // The backend translates its error messages into this language.
  headers.set("X-Language", getActiveLanguage());
  // Never force JSON on FormData uploads: the browser must set the multipart boundary itself.
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  if (init?.body && !isFormData && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  return headers;
}

function errorDetail(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (Array.isArray(detail)) return detail.map((item: { msg?: string }) => item.msg ?? String(item)).join("; ");
  return typeof detail === "string" && detail ? detail : fallback;
}

type ApiFetchOptions = {
  /** Set to false where a 401 means "wrong password" rather than "session expired". */
  redirectOnUnauthorized?: boolean;
};

export async function apiFetch<T>(path: string, init?: RequestInit, options: ApiFetchOptions = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers: buildHeaders(init) });
  if (response.status === 401 && typeof window !== "undefined" && options.redirectOnUnauthorized !== false) {
    localStorage.removeItem(STORAGE_KEYS.token);
    window.location.href = "/login";
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(errorDetail(body, translate("common.genericError")));
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

/** Upload a FormData with real progress (fetch does not expose upload progress).
 * Used for heavy media, where people need to see how much is left on slow networks. */
export function uploadWithProgress<T = unknown>(path: string, formData: FormData, onProgress: (percent: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}${path}`);
    const token = authToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.setRequestHeader("X-Language", getActiveLanguage());
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = xhr.response ? JSON.parse(xhr.response) : null;
      } catch {
        // Not JSON (e.g. an nginx error page): the generic message is used below.
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as T);
      else reject(new Error(errorDetail(body, translate("common.uploadError"))));
    };
    xhr.onerror = () => reject(new Error(translate("common.networkUploadError")));
    xhr.send(formData);
  });
}

/** Absolute ws(s):// URL for a socket, based on the browser's current origin. */
export function wsUrl(path: string): string {
  if (typeof window === "undefined") return path;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
}
