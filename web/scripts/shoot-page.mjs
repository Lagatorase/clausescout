// Screenshots one local HTML file, for the README's Excel report preview.
// Usage: node scripts/shoot-page.mjs <html file> <png out>
import { chromium } from "@playwright/test";
import { resolve } from "path";
import { pathToFileURL } from "url";

const [file, out] = process.argv.slice(2);
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 640 } });
await page.goto(pathToFileURL(resolve(file)).toString());
await page.screenshot({ path: out, fullPage: true });
await browser.close();
console.log(`Saved ${out}`);
