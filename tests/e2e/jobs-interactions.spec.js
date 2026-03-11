// Version: 0.6.17-playwright.1
const { expect, test } = require("@playwright/test");

const WEB_UI_PATH = "/pythonista_job_runner/app/webui.html";

async function stubWebUiApi(page) {
  await page.route("**/stats.json*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ queued: 1, running: 1, done: 1, errors: 1, total: 4 }),
    });
  });

  await page.route("**/jobs.json*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        jobs: [
          { job_id: "job-error-1", state: "error", created_utc: "2026-03-11T21:00:00Z", updated_utc: "2026-03-11T21:00:12Z", exit_code: 1, error: "Import failed", submitted_by: { display_name: "Alex" } },
          { job_id: "job-running-1", state: "running", created_utc: "2026-03-11T21:01:00Z", updated_utc: "2026-03-11T21:01:12Z", submitted_by: { display_name: "Blake" } },
          { job_id: "job-queued-1", state: "queued", created_utc: "2026-03-11T21:02:00Z", updated_utc: "2026-03-11T21:02:12Z", submitted_by: { display_name: "Casey" } },
          { job_id: "job-done-1", state: "done", created_utc: "2026-03-11T21:03:00Z", updated_utc: "2026-03-11T21:03:12Z", exit_code: 0, result_ready: true, submitted_by: { display_name: "Drew" } },
        ],
      }),
    });
  });

  await page.route("**/info.json*", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ service: "pythonista_job_runner" }) });
  });
}

async function openWebUi(page) {
  await stubWebUiApi(page);
  await page.goto(WEB_UI_PATH);
  await expect(page.locator("#statusline")).toHaveText(/Connected/i);
  await expect(page.locator("#jobtable tbody tr").first()).toBeVisible();
}

test("renders semantic state iconography for running/done/error/queued rows", async ({ page }) => {
  await openWebUi(page);

  await expect(page.locator("tr[data-state='running'] .badge-icon").first()).toHaveText("↻");
  await expect(page.locator("tr[data-state='done'] .badge-icon").first()).toHaveText("✓");
  await expect(page.locator("tr[data-state='error'] .badge-icon").first()).toHaveText("!");
  await expect(page.locator("tr[data-state='queued'] .badge-icon").first()).toHaveText("…");
});

test("small-screen filters summary updates and escape closes filter panel", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openWebUi(page);

  await page.locator("#filters_menu > summary").click();
  await page.fill("#filter_user", "Alex");
  await expect(page.locator("#filters_summary")).toContainText("User: Alex");

  await page.keyboard.press("Escape");
  await expect(page.locator("#filters_menu")).not.toHaveAttribute("open", "");

  await page.locator("#filters_menu > summary").focus();
  await page.keyboard.press("Enter");
  await page.locator("button[data-action='close-filters-panel']").click();
  await expect(page.locator("#filters_menu")).not.toHaveAttribute("open", "");
});

test("keyboard traversal supports row selection and strong focus visibility", async ({ page }) => {
  await openWebUi(page);

  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");

  const row = page.locator("#jobtable tbody tr").first();
  await row.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#jobid")).toContainText("job-");

  const outlineWidth = await row.evaluate((el) => getComputedStyle(el).outlineWidth);
  expect(parseFloat(outlineWidth)).toBeGreaterThanOrEqual(2);
});

test("reduced-motion mode suppresses running progress animation", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await openWebUi(page);
  const duration = await page.locator("tr[data-state='running'] .progress-bar").first().evaluate((el) => getComputedStyle(el).animationDuration);
  expect(["0.01ms", "0.00001s"]).toContain(duration);
});
