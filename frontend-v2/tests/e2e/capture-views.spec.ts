import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const advisorEmail = process.env.E2E_ADVISOR_EMAIL || "advisor@lvmh.com";
const managerEmail = process.env.E2E_MANAGER_EMAIL || "manager@lvmh.com";
const adminEmail = process.env.E2E_ADMIN_EMAIL || "admin@lvmh.com";
const password = process.env.E2E_PASSWORD || "lvmh";

const outputDir = path.resolve(process.cwd(), "..", "docs", "assets", "ui-captures-2026-02-12");

async function loginIfNeeded(page, route: string, email: string, userPassword: string) {
    for (let attempt = 0; attempt < 3; attempt += 1) {
        await page.goto(route);
        const emailInput = page.getByPlaceholder("advisor@lvmh.com");
        if (await emailInput.isVisible().catch(() => false)) {
            await emailInput.fill(email);
            await page.locator('input[type="password"]').fill(userPassword);
            await page.getByRole("button", { name: /connexion/i }).click();
        }
        await page.waitForTimeout(2500);

        const loginError = page.getByText(/identifiants incorrects/i);
        if (await loginError.isVisible().catch(() => false)) {
            continue
        }
        return;
    }
}

test("capture advisor/manager/pipeline/admin views", async ({ page }) => {
    fs.mkdirSync(outputDir, { recursive: true });

    await loginIfNeeded(page, "/advisor", advisorEmail, password);
    await expect(page.getByRole("button", { name: /mode texte/i })).toBeVisible({ timeout: 20_000 });
    await page.screenshot({ path: path.join(outputDir, "advisor.png"), fullPage: true });
    await page.getByRole("button", { name: /deconnexion/i }).first().click();
    await page.waitForTimeout(1200);

    await loginIfNeeded(page, "/manager", managerEmail, password);
    await expect(page.getByRole("button", { name: /deconnexion/i })).toBeVisible({ timeout: 20_000 });
    await page.screenshot({ path: path.join(outputDir, "manager.png"), fullPage: true });

    await page.goto("/pipeline");
    await expect(page.getByText(/pipeline monitor/i)).toBeVisible({ timeout: 20_000 });
    await page.screenshot({ path: path.join(outputDir, "pipeline.png"), fullPage: true });
    await page.getByRole("button", { name: /deconnexion/i }).first().click();
    await page.waitForTimeout(1200);

    await loginIfNeeded(page, "/admin", adminEmail, password);
    await expect(page.getByRole("button", { name: /deconnexion/i })).toBeVisible({ timeout: 20_000 });
    await page.screenshot({ path: path.join(outputDir, "admin.png"), fullPage: true });
});
