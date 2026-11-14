import { test, expect } from "@playwright/test";

test("real browser: CSP blocks same-origin base changes and fetch sends no referrer", async ({ page }) => {
  const response = await page.goto("/login");
  expect(response?.headers()["referrer-policy"]).toBe("no-referrer");
  expect(response?.headers()["content-security-policy"]).toContain("base-uri 'none'");

  const policy = await page.evaluate(async () => {
    const original = document.baseURI;
    const violation = new Promise<string>((resolve) => {
      document.addEventListener("securitypolicyviolation", (event) => resolve(event.violatedDirective), { once: true });
      setTimeout(() => resolve("missing violation"), 1_000);
    });
    const base = document.createElement("base");
    base.href = `${location.origin}/changed-base/`;
    document.head.append(base);
    const directive = await violation;
    const unchanged = document.baseURI === original;
    base.remove();
    return { directive, unchanged };
  });
  expect(policy).toEqual({ directive: "base-uri", unchanged: true });

  const sent = page.waitForRequest((request) => request.url().includes("/api/v1/health/live"));
  await page.evaluate(async () => { await fetch("/api/v1/health/live"); });
  // Chrome's request instrumentation can represent an omitted referrer as "".
  expect((await sent).headers()["referer"] ?? "").toBe("");
  const callback = await page.request.get("/api/v1/auth/callback?code=synthetic-private-code&state=synthetic-state");
  expect(callback.status()).toBeGreaterThanOrEqual(400);
  expect(callback.headers()["referrer-policy"]).toBe("no-referrer");
});
