import { expect, test, type Page } from "@playwright/test";

const PROVIDER_ID = "shanghai-electric-ipd";
const PROVIDERS_URL = "**/api/v1/auth/providers";

async function mockSsoProvider(page: Page) {
  await page.route(PROVIDERS_URL, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        providers: [
          { id: PROVIDER_ID, display_name: "数字底座", type: "oauth2" },
        ],
      }),
    }),
  );
}

test.describe("IPD SSO entry handoff", () => {
  test("starts the OAuth2 flow without a callback code", async ({ page }) => {
    await mockSsoProvider(page);
    await page.route(
      `**/api/v1/auth/oauth2/${PROVIDER_ID}/start**`,
      (route) => route.fulfill({ status: 200, body: "start intercepted" }),
    );

    await page.goto("/loginsso?next=%2Fworkspace%2Fscheduled-tasks");

    await expect(page).toHaveURL(
      new RegExp(
        `/api/v1/auth/oauth2/${PROVIDER_ID}/start\\?next=%2Fworkspace%2Fscheduled-tasks`,
      ),
    );
  });

  test("forwards the portal callback parameters to OAuth2 callback", async ({
    page,
  }) => {
    await mockSsoProvider(page);
    await page.route(
      `**/api/v1/auth/oauth2/${PROVIDER_ID}/callback**`,
      (route) => route.fulfill({ status: 200, body: "callback intercepted" }),
    );

    await page.goto(
      "/loginsso?code=portal-code&state=portal-state&tenant-id=1&organize-id=100",
    );

    await expect(page).toHaveURL(
      new RegExp(
        `/api/v1/auth/oauth2/${PROVIDER_ID}/callback\\?code=portal-code&state=portal-state&tenant-id=1&organize-id=100`,
      ),
    );
  });
});
