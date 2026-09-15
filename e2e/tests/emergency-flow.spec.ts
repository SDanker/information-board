import { test, expect } from "@playwright/test";

import { authHeaders, cleanUp, createScreen, login, uniqueSlug } from "./helpers";

// Featured events are the EMERGENCY content kind internally (API routes /emergencies).
test.describe("Featured event flow", () => {
  test("creating, broadcasting and stopping a featured event is reflected on a TV", async ({ page, context, baseURL }) => {
    await login(page);
    const headers = await authHeaders(page);
    const title = `E2E Featured event ${uniqueSlug("e2e")}`;
    const screenSlug = uniqueSlug("e2e-event-screen");
    let screenId: string | undefined;

    try {
      screenId = await createScreen(page.request, baseURL!, headers, screenSlug);

      await page.goto("/admin/content");
      await page.getByRole("button", { name: "New publication" }).click();
      await page.getByRole("button", { name: "Featured event", exact: true }).click();
      await page.getByLabel("Title", { exact: true }).fill(title);
      await page.locator('textarea[name="description"]').fill("Automated E2E test, not a real event.");
      await page.getByRole("button", { name: "Create featured event" }).click();
      await expect(page.getByText(/Featured event created/)).toBeVisible();

      const card = page.locator(".screen-card", { hasText: title });
      const tv = await context.newPage();
      await tv.goto(`/screen/${screenSlug}`);
      await expect(tv.locator(".board-emergency")).toHaveCount(0);

      await card.getByRole("button", { name: "Broadcast" }).click();
      await expect(tv.locator(".board-emergency")).toBeVisible({ timeout: 20_000 });
      await expect(tv.getByText(title)).toBeVisible();

      await card.getByRole("button", { name: "Stop" }).click();
      await expect(tv.locator(".board-emergency")).toHaveCount(0, { timeout: 20_000 });
      await tv.close();
    } finally {
      await page.request.post(`${baseURL}/api/v1/emergencies/clear-broadcast`, { headers });
      await cleanUp(page.request, baseURL!, headers, { screenId, contentTitle: title });
    }
  });
});
