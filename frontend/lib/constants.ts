// localStorage keys and intervals shared by several pages, kept in one place instead of
// repeating string literals.
export const STORAGE_KEYS = {
  token: "board_token",
  user: "board_user",
  role: "board_role",
  language: "board_language",
  branding: "board_branding",
  screenCache: (slug: string) => `board_screen_${slug}`,
  playlistCache: (slug: string) => `board_playlist_${slug}`,
} as const;

export const HEARTBEAT_INTERVAL_MS = 15_000;
export const DASHBOARD_POLL_INTERVAL_MS = 15_000;
export const PLAYLIST_POLL_INTERVAL_MS = 60_000;
export const BRANDING_POLL_INTERVAL_MS = 300_000;
// Must match ONLINE_WINDOW_SECONDS in backend/app/schemas/auth_screens.py.
export const ONLINE_THRESHOLD_SECONDS = 45;
