const puppeteer = require("puppeteer-core");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const URL = "http://127.0.0.1:8766/";
const SCRIPT = "https://script.google.com/macros/s/AKfycbTEST_123-abc/exec";
let fails = 0; const check = (c, m) => { console.log((c ? "PASS " : "FAIL ") + m); if (!c) fails++; };
const received = []; let down = false;
(async () => {
  const b = await puppeteer.launch({ executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome", headless: true, args: ["--no-sandbox"] });
  const p = await b.newPage();
  const errs = []; p.on("pageerror", (e) => errs.push(e.message));
  await p.setRequestInterception(true);
  p.on("request", (req) => {
    if (!req.url().startsWith("https://script.google.com")) return req.continue();
    const body = JSON.parse(req.postData() || "{}");
    received.push({ body, type: req.headers()["content-type"] });
    const json = (o) => req.respond({ status: 200, contentType: "application/json", headers: { "Access-Control-Allow-Origin": "*" }, body: JSON.stringify(o) });
    if (down) return req.respond({ status: 500, body: "err", headers: { "Access-Control-Allow-Origin": "*" } });
    if (body.secret !== "s3cret") return json({ ok: false, error: "wrong secret" });
    if (body.action === "ping") return json({ ok: true, sheet: "Job applications › Sheet1" });
    return json({ ok: true, ids: body.rows.map((r) => r.id) });
  });
  await p.goto(URL + "#applications", { waitUntil: "networkidle0" });
  await p.evaluate(() => localStorage.clear());
  await p.reload({ waitUntil: "networkidle0" });
  await p.type("#sheet-url", SCRIPT); await p.type("#sheet-secret", "wrong"); await p.click("#sheet-connect"); await sleep(400);
  check(await p.$eval("#sheet-on", (e) => e.hidden), "wrong secret: not connected");
  await p.$eval("#sheet-secret", (e) => (e.value = "")); await p.type("#sheet-secret", "s3cret"); await p.click("#sheet-connect"); await sleep(400);
  check(!(await p.$eval("#sheet-on", (e) => e.hidden)), "connected with right secret");
  check(received.every((r) => (r.type || "").startsWith("text/plain")), "requests are simple text/plain POSTs (no CORS preflight)");

  await p.evaluate(() => { location.hash = "#jobs"; }); await sleep(300); await p.waitForSelector("#view-jobs:not([hidden]) .co-head");
  await p.evaluate(() => { window.scrollTo(0, 0); document.querySelector("#view-jobs .co-head").click(); }); await sleep(400);
  const id = await p.$eval("[data-track]", (e) => e.dataset.track);
  const n0 = received.length;
  await p.select(`[data-track="${id}"]`, "saved"); await sleep(300);
  check(received.length === n0, "Saved does not write to the sheet");
  await p.select(`[data-track="${id}"]`, "applied"); await sleep(400);
  const add = received[received.length - 1].body;
  check(add.action === "add" && add.rows.length === 1 && add.rows[0].id === id, "Applied sends one row");
  const row = add.rows[0];
  console.log("   row:", JSON.stringify(row));
  check(/^\d{4}-\d{2}-\d{2}$/.test(row.applied) && row.company && row.title && /^[^,;]+, [^,;]+$/.test(row.location), "row has company, title, 'City, Country' and date");
  await p.select(`[data-track="${id}"]`, "interview"); await sleep(300);
  check(received.length === n0 + 1, "moving to Interview later doesn't add it again");

  down = true;
  const id2 = await p.$$eval("[data-track]", (e) => e[1].dataset.track);
  await p.select(`[data-track="${id2}"]`, "applied"); await sleep(400);
  const pend = await p.evaluate(() => JSON.parse(localStorage.getItem("tracker.sheet.v1")).pending.length);
  check(pend === 1, "failed send is queued");
  down = false;
  await p.reload({ waitUntil: "networkidle0" }); await sleep(600);
  const cfg = await p.evaluate(() => JSON.parse(localStorage.getItem("tracker.sheet.v1")));
  check(cfg.pending.length === 0 && cfg.sent.includes(id2), "queued row is sent on next load");

  const sample = await p.evaluate(async () => {
    const d = await (await fetch("data/roles.json")).json();
    const t = JSON.parse(localStorage.getItem("tracker.v1"));
    const picks = d.roles.filter((r) => r.status === "open").filter((_, i) => i % 9 === 0).slice(0, 90);
    for (const r of picks) t.items[r.id] = { status: "applied", applied: "2026-11-09", u: Date.now() };
    localStorage.setItem("tracker.v1", JSON.stringify(t));
    return picks.map((r) => ({ id: r.id, loc: r.locations, c: r.countries }));
  });
  await p.evaluate(() => { location.hash = "#applications"; }); await p.reload({ waitUntil: "networkidle0" }); await sleep(400);
  const before = received.length;
  await p.click("#sheet-backfill"); await sleep(1500);
  const rows = received.slice(before).flatMap((r) => r.body.rows || []);
  check(rows.length === sample.length, `backfill sends existing applications (${rows.length}/${sample.length})`);
  const byId = Object.fromEntries(rows.map((r) => [r.id, r.location]));
  const bad = [];
  for (const s of sample) { const out = byId[s.id] || ""; const countryOnly = !/,/.test(s.loc || "") && !/\s-\s/.test(s.loc || ""); if (!/^[^,;]+, [^,;]+$/.test(out) && !(countryOnly && out)) bad.push(`${s.loc} -> ${out}`); if (/remote/i.test(s.loc || "")) console.log(`   remote: ${s.loc} -> ${out}`); }
  for (const s of sample.slice(0, 30)) console.log(`   ${String(s.loc).slice(0, 55).padEnd(55)} -> ${byId[s.id]}`);
  check(bad.length === 0, `every location is "City, Country" (${bad.length} bad${bad.length ? ": " + bad.slice(0, 8).join(" | ") : ""})`);
  check(errs.length === 0, "no page errors " + errs.join("; "));
  await b.close();
  console.log(fails ? `${fails} FAILED` : "ALL PASSED");
})();
