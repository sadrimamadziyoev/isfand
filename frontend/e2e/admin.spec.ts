import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
// A disposable account file is prepared by ops/prepare-browser-test.py.
// It never ships in the repository or production image.
test("administrator creates a company, imports employees, drafts a campaign, and inspects results", async ({
  page,
}) => {
  const auth = JSON.parse(
    readFileSync(
      process.env.E2E_AUTH_FILE || "/tmp/awareguard-e2e-auth.json",
      "utf8",
    ),
  );
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "С возвращением" }),
  ).toBeVisible();
  await page.getByLabel("Рабочий email").fill(auth.email);
  await page.getByLabel("Пароль", { exact: true }).fill(auth.password);
  const otp = execFileSync(
    "../.venv/bin/python",
    ["-c", "import pyotp,sys;print(pyotp.TOTP(sys.argv[1]).now())", auth.mfa],
    { encoding: "utf8" },
  ).trim();
  await page.getByLabel("Код из приложения-аутентификатора").fill(otp);
  await page.getByRole("button", { name: "Войти в AwareGuard" }).click();
  await expect(
    page.getByRole("heading", { name: "Начнём с вашей первой компании" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Добавить компанию" }).click();
  await page.getByLabel("Название", { exact: true }).fill("Example Company");
  await page.getByLabel("Корпоративный домен").fill("example.com");
  await page.getByRole("button", { name: "Сохранить", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Example Company", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Сотрудники", exact: true }).click();
  await page.locator("input[type=file]").setInputFiles({
    name: "employees.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "full_name,email,department\nAlex Example,alex@example.com,Engineering\nSam Example,sam@example.com,People\n",
    ),
  });
  await expect(page.getByText("Alex Example", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Обзор кампаний", exact: false })
    .click();
  await page.getByRole("button", { name: "Создать кампанию" }).click();
  await page.getByLabel("Название кампании").fill("Проверка осознанности");
  await page.getByLabel("Шаблон письма").click();
  await page
    .getByText("Корпоративный документ", { exact: true })
    .last()
    .click();
  await page
    .getByRole("button", { name: "Выбрать всех включённых сотрудников" })
    .click();
  await page.getByRole("button", { name: "Создать черновик" }).click();
  await expect(
    page.getByText("Проверка осознанности", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Утвердить", exact: true }),
  ).toBeDisabled();
  await page.getByText("Проверка осознанности", { exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Результаты участников" }),
  ).toBeVisible();
  await expect(
    page.getByText("alex@example.com", { exact: true }),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Export CSV" }).click();
  expect((await download).suggestedFilename()).toMatch(/campaign-.*\.csv/);
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await expect(
    page.getByText("Результаты кампании", { exact: true }),
  ).toBeHidden();
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    document.querySelectorAll(".ant-table-content").forEach((el) => {
      el.scrollLeft = 0;
    });
  });
  await page.screenshot({
    animations: "disabled",
    path: "/tmp/awareguard-dashboard.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Шаблоны писем", exact: true })
    .click();
  await page.getByRole("button", { name: "Посмотреть шаблон" }).first().click();
  await expect(page.getByTitle("Безопасный просмотр шаблона")).toBeVisible();
  await page.getByRole("button", { name: "Закрыть", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    animations: "disabled",
    path: "/tmp/awareguard-mobile.png",
    fullPage: true,
  });
  await page.goto("/training-preview");
  await expect(
    page.getByRole("heading", { name: "Это была учебная симуляция фишинга." }),
  ).toBeVisible();
});
