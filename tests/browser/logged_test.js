const puppeteer = require("puppeteer-core");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let fails = 0; const check = (c, m) => { console.log((c ? "PASS " : "FAIL ") + m); if (!c) fails++; };
(async () => {
  const b = await puppeteer.launch({ executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome", headless: true, args: ["--no-sandbox"] });
  const p = await b.newPage(); const errs = []; p.on("pageerror", (e) => errs.push(e.message));
  const sent = [];
  await p.setRequestInterception(true);
  p.on("request", (req) => {
    if (!req.url().startsWith("https://script.google.com")) return req.continue();
    const body = JSON.parse(req.postData() || "{}"); sent.push(body);
    req.respond({ status: 200, contentType: "application/json", headers: { "Access-Control-Allow-Origin": "*" }, body: JSON.stringify(body.action === "ping" ? { ok: true, sheet: "S" } : { ok: true, ids: body.rows.map((r) => r.id), skipped: [] }) });
  });
  await p.setViewport({ width: 1280, height: 900 });
  await p.goto("http://127.0.0.1:8766/#jobs", { waitUntil: "networkidle0" });
  await p.evaluate(() => { localStorage.clear(); localStorage.setItem("tracker.sheet.v1", JSON.stringify({ url: "https://script.google.com/macros/s/X/exec", secret: "s", name: "S", sent: [], pending: [] })); });
  await p.reload({ waitUntil: "networkidle0" }); await p.waitForSelector(".co-head");
  await p.click(".co-head"); await sleep(300);
  const ids = await p.$$eval("[data-track]", (e) => e.map((x) => x.dataset.track));
  const opts = await p.$$eval(`[data-track="${ids[0]}"] option`, (o) => o.map((x) => x.textContent));
  check(opts.includes("Already applied"), "status menu has 'Already applied'");
  const n0 = sent.length;
  for (const id of ids) { await p.select(`[data-track="${id}"]`, "logged"); await sleep(120); }
  await sleep(300);
  check(sent.filter((x) => x.action === "add").length === 0 && sent.length === n0, "'Already applied' sends nothing to the sheet");
  const st = await p.evaluate(() => ({
    done: [...document.querySelectorAll(".co.open .role")].map((r) => r.classList.contains("done")),
    coDone: document.querySelector(".co.open").classList.contains("done"),
    pill: document.querySelector(".co.open .track .val").textContent,
  }));
  check(st.done.length && st.done.every(Boolean) && st.coDone, "roles and company are greyed out");
  check(st.pill === "Already applied", "pill reads 'Already applied'");
  await p.evaluate(() => { location.hash = "#applications"; }); await sleep(300);
  const counts = await p.$eval("#apps-counts", (e) => e.textContent);
  check(/already applied/.test(counts), `My applications counts it (${counts})`);
  await p.click("#sheet-backfill"); await sleep(400);
  check(sent.filter((x) => x.action === "add").length === 0, "'Add existing applications' skips them too");
  await p.evaluate(() => { location.hash = "#jobs"; window.scrollTo(0, 0); }); await sleep(300);
  await p.mouse.move(5, 5);
  await p.screenshot({ path: process.argv[2] });
  check(errs.length === 0, "no page errors " + errs.join("; "));
  await b.close(); console.log(fails ? `${fails} FAILED` : "ALL PASSED");
})();
