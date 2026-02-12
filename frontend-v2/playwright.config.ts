import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL || "http://127.0.0.1:3000";
const skipWebServer = process.env.E2E_SKIP_WEBSERVER === "1";

export default defineConfig({
    testDir: "./tests/e2e",
    timeout: 45_000,
    expect: {
        timeout: 10_000
    },
    fullyParallel: true,
    retries: process.env.CI ? 1 : 0,
    reporter: [["list"], ["html", { open: "never" }]],
    use: {
        baseURL,
        trace: "retain-on-failure",
        screenshot: "only-on-failure",
        video: "retain-on-failure"
    },
    projects: [
        {
            name: "chromium",
            use: { ...devices["Desktop Chrome"] }
        }
    ],
    webServer: skipWebServer
        ? undefined
        : {
              command: "npm run dev -- --host 127.0.0.1 --port 3000",
              url: baseURL,
              reuseExistingServer: !process.env.CI,
              timeout: 120_000
          }
});
