// Captures the frames for the README demo GIF from a running app (http://127.0.0.1:8000).
// Usage: node scripts/demo-frames.mjs <out-dir> <contract files...>
// Each frame is saved with how long it should show, and scripts/make_gif.py joins them.
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "fs";

const [outDir, ...files] = process.argv.slice(2);
mkdirSync(outDir, { recursive: true });
const frames = [];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 760 }, colorScheme: "light" });

async function shot(ms) {
  const path = `${outDir}/frame-${String(frames.length).padStart(2, "0")}.png`;
  await page.screenshot({ path });
  frames.push({ path, ms });
}

await page.goto("http://127.0.0.1:8000/");
await page.waitForSelector("input[type=file]");
await shot(1400);
await page.setInputFiles("input[type=file]", files);
// A frame while it works, then up to 20 minutes for the hybrid to finish on the laptop.
await page.waitForTimeout(1500);
await shot(1200);
await page.waitForSelector("mark", { timeout: 20 * 60 * 1000 });
await page.waitForTimeout(400);
await shot(1400);
// Step through quotes the way a reviewer would, with j.
for (let i = 0; i < 4; i++) {
  await page.keyboard.press("j");
  await page.waitForTimeout(700);
  await shot(900);
}
// Jump to a quote from a playbook flag.
await page.locator(".flag button").first().click();
await page.waitForTimeout(700);
await shot(1400);
// Next contract, if there is more than one, then dark mode.
if (files.length > 1) {
  await page.keyboard.press("n");
  await page.waitForSelector("mark");
  await page.waitForTimeout(500);
  await shot(1100);
}
await page.keyboard.press("t");
await page.keyboard.press("t");
await page.waitForTimeout(300);
await shot(1600);

writeFileSync(`${outDir}/frames.json`, JSON.stringify(frames, null, 1));
await browser.close();
console.log(`${frames.length} frames, ${frames.reduce((s, f) => s + f.ms, 0) / 1000} s`);
