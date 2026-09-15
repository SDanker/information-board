import { test, expect } from "@playwright/test";
import path from "path";

import { authHeaders, cleanUp, createScreen, login, uniqueSlug } from "./helpers";

// Presentations share the exact document pipeline (LibreOffice -> PDF -> WebP, see
// backend/app/worker.py:_run_conversion) already covered by document-flow.spec.ts. This test
// covers the spreadsheet table view, which follows a different code path (parse_spreadsheet).
test.describe("Spreadsheet flow", () => {
  test("an uploaded CSV is published and shown as a table on a TV", async ({ page, baseURL }) => {
    await login(page);
    const headers = await authHeaders(page);
    const title = `E2E Spreadsheet ${Date.now()}`;
    const playlistName = uniqueSlug("e2e-sheet-playlist");
    const screenSlug = uniqueSlug("e2e-sheet-screen");
    let screenId: string | undefined;

    try {
      await page.goto("/admin/content");
      await page.getByRole("button", { name: "New publication" }).click();
      await page.getByRole("button", { name: "Spreadsheet", exact: true }).click();
      await page.getByLabel("Title", { exact: true }).fill(title);
      await page.locator('input[type="file"]').setInputFiles(path.join(__dirname, "..", "fixtures", "sample-sheet.csv"));
      await page.getByRole("button", { name: "Upload file" }).click();

      const card = page.locator(".screen-card", { hasText: title });
      await expect(card.getByText(/Published/)).toBeVisible({ timeout: 45_000 });

      await page.goto("/admin/playlists");
      await page.getByRole("button", { name: "New playlist" }).click();
      await page.getByPlaceholder("Entrance rotation").fill(playlistName);
      await page.getByRole("button", { name: "Create playlist" }).click();
      await page.locator(".playlist-add-row select").selectOption({ label: title });

      screenId = await createScreen(page.request, baseURL!, headers, screenSlug);
      await page.goto("/admin/screens");
      const screenCard = page.locator(".screen-card", { hasText: screenSlug });
      await screenCard.locator("select").selectOption({ label: new RegExp(playlistName) });

      const tv = await page.context().newPage();
      await tv.goto(`/screen/${screenSlug}`);
      await expect(tv.locator(".board-slide-table")).toBeVisible({ timeout: 20_000 });
      await expect(tv.getByText("Responsable")).toBeVisible();
      await expect(tv.getByText("Ana")).toBeVisible();
      await tv.close();
    } finally {
      await cleanUp(page.request, baseURL!, headers, { screenId, playlistName, contentTitle: title });
    }
  });
});
