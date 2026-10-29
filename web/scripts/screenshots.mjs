// Takes the README screenshots from a running app (http://127.0.0.1:8000) with one contract.
// Usage: node scripts/screenshots.mjs <images-dir> <exports-dir> <contract file>
// Saves upload.png and results.png to the images folder, and the pack's Excel report to the
// exports folder, so scripts/excel_preview.py can render it for excel-preview.png.
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "fs";

const [imagesDir, exportsDir, file] = process.argv.slice(2);
mkdirSync(imagesDir, { recursive: true });
mkdirSync(exportsDir, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 800 }, colorScheme: "light" });

// The upload page before anything is dropped in.
await page.goto("http://127.0.0.1:8000/");
await page.waitForSelector("input[type=file]");
await page.screenshot({ path: `${imagesDir}/upload.png` });

// One contract through the selected method. The hybrid takes a few minutes per contract on
// the laptop, so I wait up to 20 minutes for the first highlighted quote.
await page.setInputFiles("input[type=file]", [file]);
await page.waitForSelector("mark", { timeout: 20 * 60 * 1000 });
// Jump to the quote behind the first playbook flag, so the shot shows a flagged clause.
const flag = page.locator(".flag button").first();
if (await flag.count()) {
  await flag.click();
  await page.waitForTimeout(800);
}
await page.screenshot({ path: `${imagesDir}/results.png` });

// The Excel report for this pack, through the same link the app's "Download Excel" uses.
const href = await page.locator("a", { hasText: "Download Excel" }).getAttribute("href");
const res = await page.request.get(new URL(href, page.url()).toString());
writeFileSync(`${exportsDir}/demo-report.xlsx`, await res.body());

await browser.close();
console.log(`Saved upload.png and results.png; Excel report from ${href}`);
