import { defineConfig } from "@playwright/test";

// Runs against a real stack (docker compose up -d), not a development server started by
// Playwright: document conversions and the worker only exist inside the containers.
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost";

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false, // tests share global state such as the active emergency broadcast
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
});
