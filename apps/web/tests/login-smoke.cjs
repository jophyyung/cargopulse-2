const { chromium, expect } = require("@playwright/test");
const fs = require("node:fs/promises");
(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CARGOPULSE_BROWSER_CHANNEL
      ? { channel: process.env.CARGOPULSE_BROWSER_CHANNEL }
      : {}),
  });
  const page = await browser.newPage();
  const failures = [];
  page.on("pageerror", (error) => failures.push(error.message));
  page.on("console", (message) => {
    if (/Content Security Policy|violates.*directive/i.test(message.text()))
      failures.push(message.text());
  });
  const origin = process.env.CARGOPULSE_E2E_URL || "http://127.0.0.1:3100";
  const nonces = [];
  for (const [width, height] of [
    [1280, 720],
    [1440, 900],
    [1920, 1080],
    [768, 1024],
  ]) {
    await page.setViewportSize({ width, height });
    const response = await page.goto(`${origin}/login`);
    const csp = response.headers()["content-security-policy"];
    expect(csp).toContain("'nonce-");
    expect(csp).not.toContain("'unsafe-eval'");
    expect(
      csp.split(";").find((value) => value.trim().startsWith("script-src")),
    ).not.toContain("'unsafe-inline'");
    nonces.push(csp.match(/nonce-([^']+)/)[1]);
    await expect(
      page.getByRole("heading", { name: "Sign in to CargoPulse" }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect(
      await page
        .locator("script")
        .evaluateAll((scripts) =>
          scripts.every((script) => Boolean(script.nonce)),
        ),
    ).toBe(true);
    await page.screenshot({
      path: `apps/web/evidence/login-${width}.png`,
      fullPage: true,
    });
  }
  expect(new Set(nonces).size).toBe(4);
  await page.getByRole("button", { name: "繁體中文" }).click();
  await expect(
    page.getByRole("heading", { name: "登入 CargoPulse" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "登入 CargoPulse" }),
  ).toBeVisible();
  expect(await page.locator("html").getAttribute("lang")).toBe("zh-Hant");
  await page.getByRole("button", { name: "English", exact: true }).click();
  const request = await page.request.get(
    `${origin}/api/v1/http%3A%2F%2Fexample.com`,
  );
  expect(request.status()).toBe(404);
  expect(failures).toEqual([]);
  await fs.writeFile(
    "apps/web/evidence/login-smoke.json",
    JSON.stringify(
      {
        scope:
          "Production standalone login only; no backend was running. Not an authenticated Recover end-to-end test.",
        browser: "Chromium / Chrome channel",
        sizes: [
          [1280, 720],
          [1440, 900],
          [1920, 1080],
          [768, 1024],
        ],
        nonce_unique: true,
        script_unsafe_inline: false,
        script_unsafe_eval: false,
        locale_persistence: true,
        arbitrary_proxy_route_rejected: true,
        console_csp_or_page_errors: failures,
      },
      null,
      2,
    ),
  );
  console.log(
    "Standalone login: 4 viewports, distinct CSP nonces, no script unsafe-inline/eval, script nonces present, locale survives reload, fixed proxy boundary, no page/CSP errors.",
  );
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
