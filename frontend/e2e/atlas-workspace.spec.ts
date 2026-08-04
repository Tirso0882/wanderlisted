import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("renders three chips, right-aligned user input, and honest stop behavior", async ({
  page,
}) => {
  await page.route("**/api/v1/chat/stream", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 700));
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: [
        'data: {"type":"session","session_id":"mock-session"}',
        'data: {"type":"token","token":"I will keep evidence visible."}',
        'data: {"type":"done","locale":"en","interrupted":false,"components":null,"budget":null}',
        "",
      ].join("\n\n"),
    });
  });
  await page.goto("/");
  const suggestions = page.getByLabel("Suggested follow-ups");
  await expect(suggestions.getByRole("button")).toHaveCount(3);
  await suggestions.getByRole("button").first().click();
  await expect(page.locator('[data-message-role="user"]')).toHaveClass(/atlas-message-row-user/);
  await expect(page.getByRole("button", { name: "Stop response" })).toBeVisible();
  await page.getByRole("button", { name: "Stop response" }).click();
  await expect(page.getByText("Response stopped")).toBeVisible();
});

test("uses Polish copy and exposes mobile Chat and Trip panes", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile-only contract");
  await page.context().addCookies([
    {
      name: "wanderlisted_locale",
      value: "pl",
      url: "http://localhost:3100",
      httpOnly: true,
    },
  ]);
  await page.goto("/");
  await expect(page.getByText("Dokąd ruszamy tym razem?")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Nawigacja przestrzeni podróży" })).toBeVisible();
  await page.getByRole("button", { name: "Podróż", exact: true }).click();
  await expect(page.getByText("Tutaj pojawią się szczegóły podróży")).toBeVisible();
});

test("keeps guest chat available while account history is gated", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByRole("textbox", { name: "Ask about your trip…" })).toBeVisible();

  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "Open trip history" }).click();
  }

  const history = page.getByRole("complementary", { name: "Your trips" });
  await expect(history).toBeVisible();
  await expect(
    history.getByText("Account features are not enabled in this environment. Guest chat still works."),
  ).toBeVisible();
});

test("has no serious automated accessibility violations and honors reduced motion", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations.filter((violation) => violation.impact === "serious")).toEqual([]);
  const transitionDuration = await page
    .getByRole("button", { name: "Plan a city break" })
    .evaluate((element) => getComputedStyle(element).transitionDuration);
  expect(Number.parseFloat(transitionDuration)).toBeLessThanOrEqual(0.00001);
});
