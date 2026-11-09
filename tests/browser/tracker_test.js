const puppeteer = require("puppeteer-core");
const fs = require("fs");
const path = require("path");

const URL = process.argv[2] || "http://127.0.0.1:8766/";
const TMP = process.argv[3] || ".";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let failures = 0;
const check = (cond, msg) => { console.log(`${cond ? "PASS" : "FAIL"} ${msg}`); if (!cond) failures++; };

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome", headless: true, args: ["--no-sandbox"] });
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("dialog", (d) => d.accept());
  await page.setViewport({ width: 375, height: 800 });
  await page.goto(URL + "#jobs", { waitUntil: "networkidle0" });
  await page.evaluate(() => localStorage.clear());
  await page.reload({ waitUntil: "networkidle0" });
  await page.waitForSelector(".co-head");

  const heads = await page.$$(".co-head");
  await heads[0].click();
  await heads[1].click();
  await sleep(300);
  const ids = await page.$$eval("[data-track]", (els) => els.slice(0, 3).map((e) => e.dataset.track));
  await page.select(`[data-track="${ids[0]}"]`, "applied");
  await page.select(`[data-track="${ids[1]}"]`, "interview");
  await page.select(`[data-track="${ids[2]}"]`, "rejected");
  await sleep(100);
  await page.click(`[data-note="${ids[0]}"]`);
  await sleep(100);
  await page.type(`[data-notes="${ids[0]}"]`, "Referral from Ana; OA due 3 Dec");
  await sleep(500);

  const before = await page.evaluate(() => localStorage.getItem("tracker.v1"));
  const parsed = JSON.parse(before);
  check(parsed.items[ids[0]].status === "applied", "status saved to localStorage");
  check(/^\d{4}-\d{2}-\d{2}$/.test(parsed.items[ids[0]].applied || ""), "applied date auto-set");
  check(parsed.items[ids[0]].notes === "Referral from Ana; OA due 3 Dec", "notes saved");
  check(!!parsed.items[ids[0]].snap, "snapshot stored for closed-role display");

  await page.reload({ waitUntil: "networkidle0" });
  await page.waitForSelector(".co-head");
  const after = await page.evaluate(() => localStorage.getItem("tracker.v1"));
  check(after === before, "tracker survives reload unchanged");

  await page.goto(URL + "#applications", { waitUntil: "networkidle0" });
  await sleep(200);
  const rows = await page.$$eval(".app", (els) => els.length);
  check(rows === 3, `My applications lists 3 rows (got ${rows})`);
  const counts = await page.$eval("#apps-counts", (e) => e.textContent);
  check(/3 tracked/.test(counts) && /1 applied/.test(counts) && /1 interview/.test(counts) && /1 rejected/.test(counts), `counts per status (${counts})`);
  const order = await page.$$eval(".app [data-track]", (els) => els.map((e) => e.value));
  check(order.join(",") === "interview,applied,rejected", `sorted by status (${order.join(",")})`);
  const struck = await page.$$eval(".app.rejected .role-title", (els) => els.map((e) => getComputedStyle(e).textDecorationLine));
  check(struck.length === 1 && struck[0].includes("line-through"), "rejected role title struck through");

  await page.evaluate(() => {
    window.__blobs = [];
    const orig = URL.createObjectURL;
    URL.createObjectURL = (b) => { window.__blobs.push(b); return orig(b); };
  });
  await page.click("#export");
  await sleep(200);
  const exported = await page.evaluate(async () => window.__blobs[0].text());
  const file = path.join(TMP, "export.json");
  fs.writeFileSync(file, exported);
  check(JSON.parse(exported).tracker.items[ids[1]].status === "interview", "export contains tracker");

  await page.evaluate(() => localStorage.setItem("tracker.v1", JSON.stringify({ v: 1, items: {} })));
  await page.reload({ waitUntil: "networkidle0" });
  await sleep(200);
  const emptied = await page.$$eval(".app", (els) => els.length);
  check(emptied === 0, "tracker cleared before import");

  const input = await page.$("#import-file");
  await input.uploadFile(file);
  await sleep(500);
  const restored = await page.evaluate(() => localStorage.getItem("tracker.v1"));
  check(JSON.stringify(JSON.parse(restored).items) === JSON.stringify(JSON.parse(before).items), "export → import restores the tracker exactly");
  const rows2 = await page.$$eval(".app", (els) => els.length);
  check(rows2 === 3, "My applications shows 3 rows after import");

  await page.goto(URL + "#jobs", { waitUntil: "networkidle0" });
  await page.evaluate(() => localStorage.setItem("filters.v1", JSON.stringify({ country: "noUK", status: "open" })));
  await page.reload({ waitUntil: "networkidle0" });
  const ukOnly = await page.evaluate(async () => {
    const d = await (await fetch("data/roles.json")).json();
    const ukIds = new Set(d.roles.filter((r) => r.countries.length && r.countries.every((c) => c === "GB")).map((r) => r.id));
    document.querySelectorAll(".co-head").forEach((h) => h.click());
    await new Promise((r) => setTimeout(r, 400));
    let shown = 0, leaked = 0;
    let more = document.querySelector("#more");
    while (more && !more.hidden) { more.click(); await new Promise((r) => setTimeout(r, 50)); more = document.querySelector("#more"); }
    document.querySelectorAll(".co:not(.open) .co-head").forEach((h) => h.click());
    await new Promise((r) => setTimeout(r, 400));
    document.querySelectorAll("[data-track]").forEach((s) => { shown++; if (ukIds.has(s.dataset.track)) leaked++; });
    return { shown, leaked, uk: ukIds.size };
  });
  check(ukOnly.leaked === 0 && ukOnly.shown > 0, `default view shows no UK-only role (${ukOnly.shown} shown, ${ukOnly.uk} UK-only hidden)`);

  await page.evaluate(() => { localStorage.setItem("filters.v1", JSON.stringify({ start: "july" })); });
  await page.reload({ waitUntil: "networkidle0" });
  const pressed = await page.$eval('[data-chip="start:july"]', (e) => e.getAttribute("aria-pressed"));
  const badge = await page.$eval("#filters-count", (e) => (e.hidden ? "" : e.textContent));
  check(pressed === "true" && badge === "1", `filters persist and count shows (${pressed}, badge ${badge})`);

  check(errors.length === 0, `no page errors ${errors.join("; ")}`);
  await browser.close();
  console.log(failures ? `${failures} FAILED` : "ALL PASSED");
  process.exit(failures ? 1 : 0);
})();
