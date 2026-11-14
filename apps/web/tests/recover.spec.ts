import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const evidence = path.resolve(process.cwd(), "apps/web/evidence");
async function checkAccessibility(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
}
async function capture(page: Page, name: string) {
  await mkdir(evidence, { recursive: true });
  await page.screenshot({ path: path.join(evidence, `${name}.png`), fullPage: true });
}


test("real service: import, solve, review and record an in-app decision", async ({
  page,
}) => {
  const consoleErrors: string[] = [];
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  page.on("console", (message) => {
    if (/Content Security Policy|violates.*directive/i.test(message.text()))
      consoleErrors.push(message.text());
  });
  await page.goto("/login");
  await page.getByLabel("Evaluation role").selectOption("manager");
  await page
    .getByRole("button", { name: "Enter evaluation workspace" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Recovery desk", exact: true }),
  ).toBeVisible();
  await checkAccessibility(page);
  await capture(page, "recover-operations-1440");
  await page.getByRole("button", { name: "Load synthetic fixture" }).click();
  await expect(page.getByLabel("Source snapshot JSON")).not.toHaveValue("");
  await page
    .getByRole("button", { name: "Validate input", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Commit validated source" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Commit validated source" }).click();
  await expect(
    page.getByText("Source committed", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByLabel("Committed source ID", { exact: true }),
  ).not.toHaveValue("");
  await page
    .getByLabel("Scenario title (optional)")
    .fill("Synthetic browser Recover acceptance");
  await page
    .getByRole("button", { name: /^Create scenario/ })
    .click();
  await expect(page).toHaveURL(/\/operations\/[a-f0-9-]+$/);
  await page.getByRole("tab", { name: "Overview", exact: true }).press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Candidate paths", exact: true })).toBeFocused();
  await expect(page.getByRole("tab", { name: "Candidate paths", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(
    page.getByRole("heading", { name: "Eligible paths", exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Candidate paths", exact: true }).press("End");
  await expect(page.getByRole("tab", { name: "Source & policy", exact: true })).toBeFocused();
  await page.getByRole("tab", { name: "Source & policy", exact: true }).press("ArrowLeft");
  await expect(page.getByRole("tab", { name: "Routes & cutoffs", exact: true })).toBeFocused();
  await expect(
    page.getByRole("heading", {
      name: "Urgency / cost of waiting",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Solve & compare" }),
  ).toBeEnabled();
  await checkAccessibility(page);
  await capture(page, "recover-urgency-1440");
  await page.getByRole("button", { name: "Solve & compare" }).click();
  const review = page.getByRole("link", {
    name: /^Review proposal/,
  });
  await expect(review).toBeVisible({ timeout: 90_000 });
  await review.click();
  await expect(
    page.getByRole("heading", { name: "Recovery proposal", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Independent validation PASS", { exact: true }),
  ).toBeVisible();

  await checkAccessibility(page);
  await capture(page, "recover-plan-1440");
  await page.getByLabel("Report format").selectOption("pdf");
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export report", exact: true }).click();
  await (await downloaded).saveAs(path.join(evidence, "synthetic-plan.pdf"));

  await page
    .getByLabel("Decision rationale")
    .fill(
      "Reviewed synthetic plan, independent validation, all affected denominator and exact snapshot hashes.",
    );
  await page
    .getByLabel("I verified the full snapshot and plan hashes shown above.")
    .check();
  await page
    .getByLabel("Type the exact action to confirm")
    .fill("APPROVE_IN_APP");
  await expect(
    page.getByRole("button", { name: "Record decision", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Record decision", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Immutable decision receipt",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("External write performed: NO", { exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: /Audit trail$/ }).click();
  await expect(
    page.getByRole("heading", { name: "Audit trail", exact: true }),
  ).toBeVisible();
  await checkAccessibility(page);
  await capture(page, "recover-audit-1440");
  await expect(consoleErrors).toEqual([]);
});

test("real service: unauthenticated access is redirected and production controls stay explicit", async ({
  page,
}) => {
  await page.goto("/operations");
  await expect(page).toHaveURL(/\/login$/);
  await expect(
    page.getByText("SYNTHETIC / NOT CONNECTED", { exact: true }),
  ).toBeVisible();
  await checkAccessibility(page);
  await page.getByRole("button", { name: "繁體中文", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "登入 CargoPulse", exact: true }),
  ).toBeVisible();
});

test("real service: authenticated workspace fits supported viewports", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Evaluation role").selectOption("manager");
  await page.getByRole("button", { name: "Enter evaluation workspace" }).click();
  await expect(page.getByRole("heading", { name: "Recovery desk", exact: true })).toBeVisible();
  for (const [width, height] of [[1280, 800], [1920, 1080], [768, 1024]]) {
    await page.setViewportSize({ width, height });
    await expect(page.getByRole("button", { name: /^Create scenario/ })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await checkAccessibility(page);
    await capture(page, `recover-operations-${width}`);
  }
});


test("real service: keyboard skip link, focus order and text filter are usable", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Evaluation role").selectOption("manager");
  await page.getByRole("button", { name: "Enter evaluation workspace" }).click();
  await expect(page.getByRole("heading", { name: "Recovery desk", exact: true })).toBeVisible();
  await page.goto("/operations");
  await expect(page.getByRole("button", { name: "Load synthetic fixture" })).toBeEnabled();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Refresh queue" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Search loaded incidents")).toBeFocused();
  await page.keyboard.type("keyboard-filter-no-matching-event");
  await expect(page.getByLabel("Search loaded incidents")).toHaveValue("keyboard-filter-no-matching-event");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("combobox", { name: /^State/ })).toBeFocused();
  // Native macOS select popups are outside Playwright keyboard control.
  // Functional selection uses the documented selectOption API; keyboard focus is checked above.
  await page.getByRole("combobox", { name: /^State/ }).selectOption("NEEDS_VERIFICATION");
  await expect(page.getByRole("combobox", { name: /^State/ })).toHaveValue("NEEDS_VERIFICATION");
});


test("real service: evaluation notices are readable before sign-in", async ({ page }) => {
  for (const [route, title] of [["/privacy", "Privacy & data handling"], ["/terms", "Terms of evaluation"]]) {
    await page.goto(route);
    await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    await expect(page.getByText("SYNTHETIC / NOT CONNECTED", { exact: true })).toBeVisible();
    await checkAccessibility(page);
  }
  expect((await page.request.get("/api/v1/events")).status()).toBe(401);
  await page.getByRole("link", { name: "Back to sign-in", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
});
