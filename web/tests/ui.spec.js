import {test, expect} from "@playwright/test";

test.beforeEach(async ({page}) => {
  await page.goto("./");
  await expect(page.locator("#model-status")).toContainText("Model ready");
});

test("default results and every algorithm run without browser errors", async ({page}) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await expect(page.locator(".item-card")).toHaveCount(10);
  for (const algorithm of ["ranked","tower","als","content","category_popularity","popularity","auto"]) {
    await page.locator("#algorithm").selectOption(algorithm);
    await expect(page.locator(".item-card")).toHaveCount(10);
    await expect(page.locator("#load-error")).toBeHidden();
  }
  await page.locator("summary").first().click();
  await expect(page.locator(".diagnostics").first()).toBeVisible();
  expect(errors).toEqual([]);
});

test("new-user preferences, collaborative cold fallback, and persisted session feedback", async ({page}) => {
  await page.getByRole("button", {name:"New user",exact:true}).click();
  await expect(page.locator("#fallback-notice")).toContainText("Popularity fallback");
  await page.getByRole("button", {name:"Books",exact:true}).click();
  await page.locator("#algorithm").selectOption("als");
  await expect(page.locator("#effective-model")).toHaveText("Content");
  await expect(page.locator("#fallback-notice")).toContainText("Content fallback");
  const first = page.locator(".item-card").first();
  const liked = await first.locator("[data-like]").getAttribute("data-like");
  await first.locator("[data-like]").click();
  await expect(page.locator("#feedback-toast")).toContainText("Liked");
  await expect(page.locator(`[data-like="${liked}"]`)).toHaveCount(0);
  await page.reload();
  await expect(page.locator("#model-status")).toContainText("Model ready");
  await page.getByRole("button", {name:"New user",exact:true}).click();
  await expect(page.locator(`[data-like="${liked}"]`)).toHaveCount(0);
  await page.getByRole("button", {name:"Reset this profile's feedback"}).click();
  await expect(page.locator("#feedback-toast")).toContainText("reset");
});

test("category, held-out filtering, evidence, and provenance views work", async ({page}) => {
  await page.locator("#category").selectOption("gaming");
  await page.locator("#cold-only").check();
  const categories = await page.locator(".item-category").allTextContents();
  expect(categories.length).toBeGreaterThan(0);
  expect(categories.every(value => value === "gaming")).toBe(true);
  await expect(page.locator(".cold-badge")).toHaveCount(categories.length);
  await page.getByRole("button", {name:"Evidence",exact:true}).click();
  await expect(page.locator("#quality-table tr")).toHaveCount(6);
  await expect(page.locator("#finding")).toContainText("popularity baseline won");
  await expect(page.locator("#selection-summary")).toContainText("Validation chose Two-tower");
  await expect(page.locator("#tradeoff-table tr")).toHaveCount(6);
  await expect(page.locator("#cohort-warning")).toContainText("30 returning users");
  await page.locator("#dataset").selectOption("amazon");
  await expect(page.locator("#selection-summary")).toContainText("Validation chose Popularity");
  await expect(page.locator("#finding")).toContainText("too sparse");
  await page.getByRole("button", {name:"System",exact:true}).click();
  await expect(page.locator("#provenance")).toContainText("synthetic-v1");
  await expect(page.locator("#provenance")).toContainText("Browser local storage");
});

test("mobile layout fits, and corrupt stored feedback cannot break model loading", async ({page}) => {
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(() => localStorage.setItem("atlas.browser.feedback.v1", '{"new-user":"corrupt"}'));
  await page.reload();
  await expect(page.locator("#model-status")).toContainText("Model ready");
  await page.getByRole("button", {name:"New user",exact:true}).click();
  await expect(page.locator(".item-card")).toHaveCount(10);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  expect(overflow).toBe(false);
  await expect(page.locator("#load-error")).toBeHidden();
});
