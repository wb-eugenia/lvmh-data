import { expect, test } from "@playwright/test";

const advisorEmail = process.env.E2E_ADVISOR_EMAIL || "advisor@lvmh.com";
const advisorPassword = process.env.E2E_ADVISOR_PASSWORD || "lvmh";
const deterministicNote =
    process.env.E2E_ADVISOR_NOTE ||
    "Cliente recherche un sac noir et une ceinture assortie, budget 3000 EUR.";

test.setTimeout(120_000);

test("advisor deterministic text flow: login -> analyze -> verify -> logout", async ({ page }) => {
    await page.goto("/advisor");

    await page.getByPlaceholder("advisor@lvmh.com").fill(advisorEmail);
    await page.locator('input[type="password"]').fill(advisorPassword);
    await page.getByRole("button", { name: /connexion/i }).click();

    await expect(page.getByRole("button", { name: /mode texte/i })).toBeVisible();
    await page.getByRole("button", { name: /mode texte/i }).click();

    await expect(page.getByText(/validation transcription/i)).toBeVisible();
    await page.getByPlaceholder(/transcription apparait ici/i).fill(deterministicNote);
    await page.getByRole("button", { name: /lancer l analyse/i }).click();

    await expect(page.getByText(/synthese client et recommandations/i)).toBeVisible({ timeout: 90_000 });
    await expect(page.getByText(/rgpd/i)).toBeVisible();
    await page.getByRole("button", { name: /terminer/i }).click();

    await page.getByRole("button", { name: /deconnexion/i }).first().click();
    await expect(page.getByText(/espace vendeur/i)).toBeVisible();
});
