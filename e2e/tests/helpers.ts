import { APIRequestContext, Page, expect } from "@playwright/test";

/** Credentials come from environment variables and are never stored in the repository. */
export function adminCredentials(): { username: string; password: string } {
  const username = process.env.E2E_ADMIN_USERNAME;
  const password = process.env.E2E_ADMIN_PASSWORD;
  if (!username || !password) {
    throw new Error("Set E2E_ADMIN_USERNAME and E2E_ADMIN_PASSWORD before running the E2E tests.");
  }
  return { username, password };
}

/** Force the English interface so selectors match whatever the installation's default language is. */
export async function useEnglish(page: Page): Promise<void> {
  await page.context().addInitScript(() => window.localStorage.setItem("board_language", "en"));
}

export async function login(page: Page): Promise<void> {
  const { username, password } = adminCredentials();
  await useEnglish(page);
  await page.goto("/login");
  await page.getByPlaceholder("Your username").fill(username);
  await page.getByPlaceholder("Your password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/admin$/);
}

export async function authHeaders(page: Page): Promise<Record<string, string>> {
  const token = await page.evaluate(() => localStorage.getItem("board_token"));
  return { Authorization: `Bearer ${token}` };
}

export function uniqueSlug(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}`;
}

/** Create a screen dedicated to one test through the API and return its id. */
export async function createScreen(request: APIRequestContext, baseURL: string, headers: Record<string, string>, slug: string): Promise<string> {
  const response = await request.post(`${baseURL}/api/v1/screens`, {
    headers,
    data: { name: `E2E ${slug}`, slug, description: "", expected_resolution: "1920x1080", orientation: "landscape", is_active: true },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).id;
}

/** Delete, through the API, whatever a test created (missing items are ignored). */
export async function cleanUp(
  request: APIRequestContext,
  baseURL: string,
  headers: Record<string, string>,
  created: { screenId?: string; playlistName?: string; contentTitle?: string },
): Promise<void> {
  if (created.screenId) await request.delete(`${baseURL}/api/v1/screens/${created.screenId}`, { headers });
  if (created.playlistName) {
    const playlists = await (await request.get(`${baseURL}/api/v1/playlists`, { headers })).json();
    const playlist = playlists.find((item: { name: string }) => item.name === created.playlistName);
    if (playlist) await request.delete(`${baseURL}/api/v1/playlists/${playlist.id}`, { headers });
  }
  if (created.contentTitle) {
    const contents = await (await request.get(`${baseURL}/api/v1/content`, { headers })).json();
    const content = contents.find((item: { title: string }) => item.title === created.contentTitle);
    if (content) await request.delete(`${baseURL}/api/v1/content/${content.id}`, { headers });
  }
}
