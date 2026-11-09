const puppeteer = require("puppeteer-core");
const path = require("path");

const OUT = process.argv[2] || ".";
const URL = process.argv[3] || "http://127.0.0.1:8765/";

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome", headless: true, args: ["--no-sandbox"] });
  const errors = [];
  const requests = new Set();
  for (const scheme of ["light", "dark"]) {
    for (const [w, h] of [[375, 812], [1280, 900]]) {
      const page = await browser.newPage();
      page.on("console", (m) => { if (m.type() === "error") errors.push(`${scheme} ${w}: ${m.text()}`); });
      page.on("pageerror", (e) => errors.push(`${scheme} ${w}: ${e.message}`));
      page.on("request", (r) => requests.add(new globalThis.URL(r.url()).host));
      await page.setViewport({ width: w, height: h, deviceScaleFactor: 1 });
      await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: scheme }]);
      await page.goto(URL + "#jobs", { waitUntil: "networkidle0" });
      await page.evaluate(() => localStorage.clear());
      await page.reload({ waitUntil: "networkidle0" });
      await page.waitForSelector(".co");
      await page.click(".co-head");
      await new Promise((r) => setTimeout(r, 300));
      const sel = await page.$("[data-track]");
      if (sel) await page.select("[data-track]", "applied");
      await new Promise((r) => setTimeout(r, 200));
      const scroll = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      if (scroll) errors.push(`${scheme} ${w}: horizontal scroll`);
      await page.screenshot({ path: path.join(OUT, `jobs-${scheme}-${w}.png`) });
      await page.click("#filters-btn");
      await new Promise((r) => setTimeout(r, 200));
      await page.screenshot({ path: path.join(OUT, `filters-${scheme}-${w}.png`) });
      await page.keyboard.press("Escape");
      await page.goto(URL + "#watchlist", { waitUntil: "networkidle0" });
      await page.screenshot({ path: path.join(OUT, `watch-${scheme}-${w}.png`) });
      await page.goto(URL + "#applications", { waitUntil: "networkidle0" });
      await new Promise((r) => setTimeout(r, 200));
      await page.screenshot({ path: path.join(OUT, `apps-${scheme}-${w}.png`) });
      await page.close();
    }
  }
  await browser.close();
  console.log("hosts:", [...requests].join(", "));
  console.log(errors.length ? errors.join("\n") : "no console errors");
})();
