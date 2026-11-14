import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  testMatch: "**/*.spec.ts",
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: process.env.CARGOPULSE_E2E_URL || "http://127.0.0.1:3000",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
    ...(process.env.CARGOPULSE_BROWSER_CHANNEL
      ? { channel: process.env.CARGOPULSE_BROWSER_CHANNEL }
      : {}),
  },
  reporter: [["list"]],
});
