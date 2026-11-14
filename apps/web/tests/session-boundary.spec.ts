import { test, expect, type Page } from "@playwright/test";

const privateConsole = (page: Page) => page.getByTestId("private-console");
const boundary = (page: Page) => page.getByTestId("session-boundary");

async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Evaluation role").selectOption("manager");
  await page.getByRole("button", { name: "Enter evaluation workspace" }).click();
  await expect(privateConsole(page)).toBeVisible();
  await expect(page.getByLabel("Source snapshot JSON")).toBeVisible();
}

async function draft(page: Page) {
  const field = page.getByLabel("Source snapshot JSON");
  await field.fill("private-unsaved-draft");
  const element = await field.elementHandle();
  if (!element) throw new Error("Expected private draft textarea");
  return element;
}

test("real service: logout unmounts both tabs and preserves unrelated storage", async ({ page, context }) => {
  await signIn(page);
  const firstDraft = await draft(page);
  await page.evaluate(() => {
    localStorage.setItem("unrelated-preference", "preserve-me");
    sessionStorage.setItem("unrelated-tab-preference", "preserve-me");
  });
  const other = await context.newPage();
  await other.goto("/operations");
  await expect(privateConsole(other)).toBeVisible();
  const secondDraft = await draft(other);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(privateConsole(page)).toHaveCount(0);
  await expect(privateConsole(other)).toHaveCount(0);
  expect(await firstDraft.evaluate((node) => node.isConnected)).toBe(false);
  expect(await secondDraft.evaluate((node) => node.isConnected)).toBe(false);
  await expect(page.getByRole("heading", { name: "Signed out", exact: true })).toBeVisible();
  expect((await page.request.get("/api/v1/me")).status()).toBe(401);
  expect(await page.evaluate(() => localStorage.getItem("unrelated-preference"))).toBe("preserve-me");
  expect(await page.evaluate(() => sessionStorage.getItem("unrelated-tab-preference"))).toBe("preserve-me");
  await signIn(page);
  await other.goto("/operations");
  await expect(privateConsole(other)).toBeVisible();
  // Inject a queued older lock notification while the current marker already
  // reflects a new login. Reading only current storage would miss this boundary.
  await other.evaluate(() => {
    const key = "cargopulse.session-boundary.v1";
    const current = JSON.parse(localStorage.getItem(key)!);
    window.dispatchEvent(new StorageEvent("storage", {
      key, newValue: JSON.stringify({ ...current, state: 1 }),
    }));
  });
  await expect(privateConsole(other)).toHaveCount(0);
  await other.close();
});

test("real login with injected logout transport failure: DOM clears without claiming revocation", async ({ page }) => {
  await signIn(page);
  const element = await draft(page);
  await page.route("**/api/v1/auth/logout", (route) => route.abort("failed"));
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(privateConsole(page)).toHaveCount(0);
  expect(await element.evaluate((node) => node.isConnected)).toBe(false);
  await expect(boundary(page).getByRole("status")).toContainText("Server sign-out is not confirmed");
  await expect(page.getByRole("heading", { name: "Signed out", exact: true })).toHaveCount(0);
  // The existing server session really remains valid. Reload must still redact it.
  expect((await page.request.get("/api/v1/me")).status()).toBe(200);
  await page.getByRole("button", { name: "繁體中文", exact: true }).click();
  await expect(page.getByRole("heading", { name: "私人工作區已隱藏", exact: true })).toBeVisible();
  await expect(boundary(page).getByRole("status")).toContainText("尚未確認伺服器登出");
  await page.getByRole("button", { name: "English", exact: true }).click();
  await page.unroute("**/api/v1/auth/logout");
  await page.reload();
  await expect(boundary(page)).toBeVisible();
  await expect(privateConsole(page)).toHaveCount(0);
  await signIn(page);
  await expect(page.getByLabel("Source snapshot JSON")).toHaveValue("");
});

test("real service: a received session 401 unmounts the console", async ({ page }) => {
  await signIn(page);
  const element = await draft(page);
  // Revoke through the real HTTP endpoint, without SQL or changing identity grants.
  const csrf = await (await page.request.get("/api/v1/auth/csrf")).json();
  const revoked = await page.request.post("/api/v1/auth/logout", {
    headers: { Origin: new URL(page.url()).origin, "X-CSRF-Token": csrf.csrf },
  });
  expect(revoked.status()).toBe(200);
  await page.getByRole("button", { name: "Load synthetic fixture", exact: true }).click();
  await expect(privateConsole(page)).toHaveCount(0);
  expect(await element.evaluate((node) => node.isConnected)).toBe(false);
  await expect(boundary(page).getByRole("status")).toContainText("session needs to be verified again");
});

test("expiry-header injection: foreground DOM clears on its timer without another request", async ({ page }) => {
  await signIn(page);
  await page.route("**/api/v1/auth/csrf", async (route) => {
    const response = await route.fetch();
    expect(response.status()).toBe(200);
    expect(response.headers()["x-session-expires-in"]).toMatch(/^[0-9]+$/);
    await route.fulfill({
      response, headers: { ...response.headers(), "x-session-expires-in": "4" },
    });
  });
  // A static console page has no data-polling hook. Only TTL metadata is
  // injected; the real backend response body/session remain unchanged.
  await page.bringToFront();
  await page.goto("/help");
  await expect(privateConsole(page)).toBeVisible();
  const element = await privateConsole(page).elementHandle();
  if (!element) throw new Error("Expected private console subtree");
  const focus = await page.evaluate(() => document.hasFocus());
  expect(focus).toBe(true);
  let requests = 0;
  const count = (request: { url(): string }) => {
    if (new URL(request.url()).pathname.startsWith("/api/v1/")) requests += 1;
  };
  page.on("request", count);
  // No RPC, tab switch or focus event is used to trigger redaction.
  await expect(privateConsole(page)).toHaveCount(0, { timeout: 6000 });
  page.off("request", count);
  expect(requests).toBe(0);
  expect(await element.evaluate((node) => node.isConnected)).toBe(false);
  await expect(boundary(page).getByRole("status")).toContainText("session needs to be verified again");
  // This is a client deadline probe, not an actual backend absolute-expiry test.
  expect((await page.request.get("/api/v1/me")).status()).toBe(200);
});

test("real service: offline redaction stays closed after reconnect/reload until fresh login", async ({ page, context }) => {
  await signIn(page);
  const element = await draft(page);
  try {
    await context.setOffline(true);
    await expect(privateConsole(page)).toHaveCount(0);
    expect(await element.evaluate((node) => node.isConnected)).toBe(false);
    await expect(boundary(page).getByRole("status")).toContainText("You are offline");
    expect(await page.evaluate(() => Object.keys(JSON.parse(
      localStorage.getItem("cargopulse.session-boundary.v1")!,
    )).sort())).toEqual(["epoch", "fingerprint", "state", "v"]);
  } finally {
    await context.setOffline(false);
  }
  await page.reload();
  await expect(boundary(page)).toBeVisible();
  await expect(privateConsole(page)).toHaveCount(0);
  expect((await page.request.get("/api/v1/me")).status()).toBe(200);
  await signIn(page);
  await expect(page.getByLabel("Source snapshot JSON")).toHaveValue("");
});

test("browser event coverage: persisted pagehide/pageshow redact the restored subtree", async ({ page }) => {
  await signIn(page);
  const element = await draft(page);
  // Explicit event injection: this tests handlers, not native BFCache eligibility.
  await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent("pagehide", { persisted: true })));
  await expect(privateConsole(page)).toHaveCount(0);
  expect(await element.evaluate((node) => node.isConnected)).toBe(false);
  await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent("pageshow", { persisted: true })));
  await expect(privateConsole(page)).toHaveCount(0);
  await page.reload();
  await expect(boundary(page)).toBeVisible();
  await expect(privateConsole(page)).toHaveCount(0);
});

test("real service: authenticated POST reads JSON CSRF even when a cookie value is wrong", async ({ page, context }) => {
  await signIn(page);
  await context.addCookies([{ name: "cp_csrf", value: "ignore-this-cookie-value", url: page.url() }]);
  const order: string[] = [];
  let usedCookie = false;
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/api/v1/auth/csrf") order.push("csrf");
    if (new URL(request.url()).pathname === "/api/v1/auth/logout" && request.method() === "POST") {
      order.push("logout");
      usedCookie = request.headers()["x-csrf-token"] === "ignore-this-cookie-value";
    }
  });
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Signed out", exact: true })).toBeVisible();
  expect(order.indexOf("csrf")).toBeGreaterThanOrEqual(0);
  expect(order.indexOf("logout")).toBeGreaterThan(order.indexOf("csrf"));
  expect(usedCookie).toBe(false);
});

test("SSO preflight branch: abandoned flow stays closed; callback-equivalent fresh session can reopen", async ({ page }) => {
  await signIn(page);
  // The actual IdP remains external. Only its navigation is intercepted here.
  await page.route("**/api/v1/auth/login", (route) => route.fulfill({
    contentType: "text/html", body: "<main>Recorded identity-provider navigation</main>",
  }));
  await page.goto("/login");
  await page.getByRole("link", { name: "Continue with organisation SSO" }).click();
  await expect(page).toHaveURL(/\/api\/v1\/auth\/login$/);
  await page.goto("/operations");
  await expect(boundary(page)).toBeVisible();
  await expect(privateConsole(page)).toHaveCount(0);
  // Issue a genuinely new session using the development adapter, then perform
  // the same full-document return used by OIDC callback. No client reset helper.
  const result = await page.request.post("/api/v1/auth/development", {
    headers: { Origin: new URL(page.url()).origin }, data: { identity_id: "manager" },
  });
  expect(result.status()).toBe(200);
  await page.goto("/operations");
  await expect(privateConsole(page)).toBeVisible();
});
