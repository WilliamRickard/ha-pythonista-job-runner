// Version: 0.6.17-playwright.1
const { expect, test } = require("@playwright/test");

const WEB_UI_PATH = "/pythonista_job_runner/app/webui.html";

async function stubWebUiApi(page) {
  await page.route("**/stats.json", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ queued: 0, running: 0, done: 2, errors: 0, total: 2 }),
    });
  });

  await page.route("**/jobs.json", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        jobs: [
          {
            id: "job-1",
            state: "done",
            created_utc: "2026-03-11T21:00:00Z",
            updated_utc: "2026-03-11T21:00:12Z",
            exit_code: 0,
            submitted_by: { display_name: "Will" },
          },
        ],
      }),
    });
  });

  await page.route("**/info.json", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        service: "pythonista_job_runner",
        version: "0.6.17",
        python: "3.13",
        endpoints: {
          health: "GET /health",
          jobs: "GET /jobs.json",
          stats: "GET /stats.json",
          info: "GET /info.json",
        },
      }),
    });
  });
}

async function openWebUi(page) {
  await stubWebUiApi(page);
  await page.goto(WEB_UI_PATH);
  await expect(page.getByText("Connected")).toBeVisible();
}

function headerPanel(page) {
  return page.locator("#header_more_panel");
}

function moreButton(page) {
  return page.locator("#header_more_toggle");
}

test.describe("header More menu", () => {
  test("stays hidden on first load and toggles open then closed", async ({ page }) => {
    await openWebUi(page);

    await expect(headerPanel(page)).toBeHidden();
    await moreButton(page).click();
    await expect(headerPanel(page)).toBeVisible();
    await moreButton(page).click();
    await expect(headerPanel(page)).toBeHidden();
  });

  test("closes when tapping outside the menu", async ({ page }) => {
    await openWebUi(page);

    await moreButton(page).click();
    await expect(headerPanel(page)).toBeVisible();
    await page.locator("#overview").click();
    await expect(headerPanel(page)).toBeHidden();
  });

  test("opens the Settings modal from the More menu", async ({ page }) => {
    await openWebUi(page);

    await moreButton(page).click();
    await page.locator("#header_more_settings").click();
    await expect(headerPanel(page)).toBeHidden();
    await expect(page.locator("#settings_overlay")).toBeVisible();
    await expect(page.getByRole("dialog", { name: "Settings" })).toBeVisible();
  });

  test("opens the Command modal from the More menu", async ({ page }) => {
    await openWebUi(page);

    await moreButton(page).click();
    await page.locator("#header_more_command").click();
    await expect(headerPanel(page)).toBeHidden();
    await expect(page.locator("#command_overlay")).toBeVisible();
    await expect(page.getByRole("dialog", { name: "Command menu" })).toBeVisible();
  });

  test("opens the Help modal from the More menu", async ({ page }) => {
    await openWebUi(page);

    await moreButton(page).click();
    await page.locator("#header_more_help").click();
    await expect(headerPanel(page)).toBeHidden();
    await expect(page.locator("#about_overlay")).toBeVisible();
    await expect(page.getByRole("dialog", { name: "Help" })).toBeVisible();
  });
});
