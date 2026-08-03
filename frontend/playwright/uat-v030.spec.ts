import { expect, test } from "@playwright/test";

/** v030-U1: Dashboard shows active execution count */
test("dashboard active execution count", async ({ page }) => {
  await page.route("**/version", (route) =>
    route.fulfill({ json: { version: "0.3.0" } }),
  );
  await page.route("**/api/v1/executions/**", (route) => {
    const url = route.request().url();
    if (url.includes("status=RUNNING")) {
      return route.fulfill({
        json: [{ execution_id: "e1", journey_id: "j1", status: "RUNNING" }],
      });
    }
    if (url.includes("status=FAILED")) {
      return route.fulfill({ json: [] });
    }
    return route.fulfill({
      json: [{ execution_id: "e1", journey_id: "j1", status: "RUNNING" }],
    });
  });

  await page.goto("/");
  await expect(page.getByTestId("active-execution-count")).toHaveText("1");
});

/** v030-U4: Journey Studio validate DSL */
test("journey studio validate DSL", async ({ page }) => {
  await page.route("**/version", (route) => route.fulfill({ json: { version: "0.3.0" } }));
  await page.route("**/api/v1/journeys/validate**", (route) =>
    route.fulfill({ json: { valid: true, errors: [], warnings: [] } }),
  );
  await page.route("**/api/v1/tools**", (route) =>
    route.fulfill({ json: { tools: [], total: 0 } }),
  );
  await page.route("**/api/v1/executions/**", (route) => route.fulfill({ json: [] }));

  await page.goto("/journeys/new/studio");
  await page.getByTestId("validate-dsl").click();
  await expect(page.getByTestId("validation-result")).toContainText("valid");
});

/** v030-U5: Tool picker lists published tools */
test("tool picker lists tools", async ({ page }) => {
  await page.route("**/version", (route) => route.fulfill({ json: { version: "0.3.0" } }));
  await page.route("**/api/v1/tools**", (route) =>
    route.fulfill({
      json: {
        tools: [{ id: "echo", version: "1", display_name: "Echo", domain: "demo" }],
        total: 1,
      },
    }),
  );
  await page.route("**/api/v1/executions/**", (route) => route.fulfill({ json: [] }));

  await page.goto("/journeys/new/studio");
  await expect(page.getByTestId("tool-picker")).toContainText("Echo");
});

/** v030-U6: Tools catalog read-only page */
test("tools catalog page", async ({ page }) => {
  await page.route("**/version", (route) => route.fulfill({ json: { version: "0.3.0" } }));
  await page.route("**/api/v1/tools**", (route) =>
    route.fulfill({
      json: {
        tools: [{ id: "ping", version: "1", display_name: "Ping", domain: "ops" }],
        total: 1,
      },
    }),
  );
  await page.route("**/api/v1/executions/**", (route) => route.fulfill({ json: [] }));

  await page.goto("/tools");
  await expect(page.getByTestId("tools-catalog")).toContainText("Ping");
});

/** v030-U7: keyboard nav primary flows */
test("keyboard navigation sidebar", async ({ page }) => {
  await page.route("**/version", (route) => route.fulfill({ json: { version: "0.3.0" } }));
  await page.route("**/api/v1/**", (route) => route.fulfill({ json: [] }));

  await page.goto("/");
  await page.keyboard.press("Tab");
  const focused = page.locator(":focus");
  await expect(focused).toBeVisible();
});
