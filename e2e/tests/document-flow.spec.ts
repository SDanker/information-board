import { test, expect } from "@playwright/test";
import path from "path";

import { authHeaders, cleanUp, createScreen, login, uniqueSlug } from "./helpers";

test.describe("Document flow", () => {
  test("upload a document, add it to a playlist and see it on a TV", async ({ page, baseURL }) => {
    await login(page);
    const headers = await authHeaders(page);
    const title = `E2E Document ${Date.now()}`;
    const playlistName = uniqueSlug("e2e-playlist");
    const screenSlug = uniqueSlug("e2e-screen");
    let screenId: string | undefined;

    try {
      // 1) Upload the document as a publication.
      await page.goto("/admin/content");
      await page.getByRole("button", { name: "New publication" }).click();
      await page.getByRole("button", { name: "Document", exact: true }).click();
      await page.getByLabel("Title", { exact: true }).fill(title);
      await page.locator('input[type="file"]').setInputFiles(path.join(__dirname, "..", "fixtures", "sample-document.txt"));
      await page.getByRole("button", { name: "Upload file" }).click();
      await expect(page.getByText("File uploaded. Processing…")).toBeVisible();

      // 2) Wait for the real worker to convert it (LibreOffice + PyMuPDF).
      const card = page.locator(".screen-card", { hasText: title });
      await expect(card.getByText(/Published/)).toBeVisible({ timeout: 45_000 });

      // 3) Create a playlist and add the document.
      await page.goto("/admin/playlists");
      await page.getByRole("button", { name: "New playlist" }).click();
      await page.getByPlaceholder("Entrance rotation").fill(playlistName);
      await page.getByRole("button", { name: "Create playlist" }).click();
      await page.locator(".playlist-add-row select").selectOption({ label: title });
      await expect(page.locator(".playlist-item-info", { hasText: title })).toBeVisible();

      // 4) Create a screen for this test and assign the playlist to it.
      screenId = await createScreen(page.request, baseURL!, headers, screenSlug);
      await page.goto("/admin/screens");
      const screenCard = page.locator(".screen-card", { hasText: screenSlug });
      await screenCard.locator("select").selectOption({ label: new RegExp(playlistName) });

      // 5) Open the TV and check that the converted page is shown.
      const tv = await page.context().newPage();
      await tv.goto(`/screen/${screenSlug}`);
      await expect(tv.locator(".board-slide-document img")).toBeVisible({ timeout: 20_000 });
      await tv.close();
    } finally {
      await cleanUp(page.request, baseURL!, headers, { screenId, playlistName, contentTitle: title });
    }
  });
});
