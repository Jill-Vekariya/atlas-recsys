import {defineConfig} from "@playwright/test";

const remote = process.env.ATLAS_DEMO_URL;
export default defineConfig({
  testDir: "tests",
  testMatch: "ui.spec.js",
  timeout: 30000,
  workers: 1,
  reporter: [["list"], ["json", {outputFile: "test-results/ui-report.json"}]],
  use: {
    baseURL: remote || "http://127.0.0.1:4173/atlas-recsys/",
    channel: process.env.ATLAS_BROWSER_CHANNEL || undefined,
    viewport: {width: 1440, height: 1000},
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: remote ? undefined : {
    command: "node tests/serve.js",
    url: "http://127.0.0.1:4173/atlas-recsys/",
    reuseExistingServer: false,
  },
});
