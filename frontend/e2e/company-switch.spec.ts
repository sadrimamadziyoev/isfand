import {
  test,
  expect,
  type Page,
  type Route,
  type Response,
} from "@playwright/test";

test.setTimeout(20000);

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

const employees = (id: string) => [
  {
    id: `${id}-employee`,
    full_name: id === "a" ? "Person Alpha" : "Person Beta",
    email: `${id}@example.com`,
    department: "IT",
    excluded: false,
  },
];
const companies = ["a", "b"].map((id) => ({
  id,
  name: id === "a" ? "Company Alpha" : "Company Beta",
  domain: "example.com",
  authorization: "",
  infrastructure_approved: false,
  blocked: false,
  domain_verified: false,
  employees: 1,
  approved_senders: [],
}));

async function mockWorkspace(
  page: Page,
  employeeRoute: (route: Route, id: string) => Promise<void>,
) {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/auth/me")
      return route.fulfill({
        json: { email: "admin@example.com", csrf: "test-csrf" },
      });
    if (url.pathname === "/api/companies")
      return route.fulfill({ json: companies });
    if (url.pathname === "/api/employees")
      return employeeRoute(route, url.searchParams.get("company_id")!);
    return route.fulfill({ json: [] });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Сотрудники", exact: true }).click();
}

async function selectBeta(page: Page) {
  await page.getByLabel("Выбрать компанию", { exact: true }).first().click();
  await page.getByText("Company Beta", { exact: true }).last().click();
}

async function settleResponse(page: Page, response: Response) {
  await response.finished();
  // Allow fetch JSON parsing and React's render to complete after the response.
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
}

test("a late old-company response cannot overwrite the selected company's employees", async ({
  page,
}) => {
  const oldRequest = deferred();
  const releaseOld = deferred();
  await mockWorkspace(page, async (route, id) => {
    if (id === "a") {
      oldRequest.resolve();
      await releaseOld.promise;
    }
    await route.fulfill({ json: employees(id) });
  });
  await oldRequest.promise;
  await selectBeta(page);
  await expect(page.getByText("Person Beta", { exact: true })).toBeVisible();
  const oldResponse = page.waitForResponse((r) =>
    r.url().includes("/api/employees?company_id=a"),
  );
  releaseOld.resolve();
  await settleResponse(page, await oldResponse);
  await expect(page.getByText("Person Beta", { exact: true })).toBeVisible();
  await expect(page.getByText("Person Alpha", { exact: true })).toBeHidden();
});

test("old-company errors cannot clear the new company's loading state or show stale errors", async ({
  page,
}) => {
  const oldRequest = deferred();
  const newRequest = deferred();
  const releaseOld = deferred();
  const releaseNew = deferred();
  await mockWorkspace(page, async (route, id) => {
    if (id === "a") {
      oldRequest.resolve();
      await releaseOld.promise;
      await route.fulfill({
        status: 503,
        json: { detail: "Old company unavailable" },
      });
    } else {
      newRequest.resolve();
      await releaseNew.promise;
      await route.fulfill({ json: employees(id) });
    }
  });
  await oldRequest.promise;
  await selectBeta(page);
  await newRequest.promise;
  const oldResponse = page.waitForResponse((r) =>
    r.url().includes("/api/employees?company_id=a"),
  );
  releaseOld.resolve();
  await settleResponse(page, await oldResponse);
  await expect(page.locator(".ant-spin-spinning")).toBeVisible();
  await expect(
    page.getByText("Old company unavailable", { exact: true }),
  ).toBeHidden();
  releaseNew.resolve();
  await expect(page.getByText("Person Beta", { exact: true })).toBeVisible();
});

test("switching companies clears the previous company's rows while the new data loads", async ({
  page,
}) => {
  const newRequest = deferred();
  const releaseNew = deferred();
  await mockWorkspace(page, async (route, id) => {
    if (id === "b") {
      newRequest.resolve();
      await releaseNew.promise;
    }
    await route.fulfill({ json: employees(id) });
  });
  await expect(page.getByText("Person Alpha", { exact: true })).toBeVisible();
  await selectBeta(page);
  await newRequest.promise;
  await expect(page.getByText("Person Alpha", { exact: true })).toBeHidden();
  releaseNew.resolve();
  await expect(page.getByText("Person Beta", { exact: true })).toBeVisible();
});
