const puppeteer = require("puppeteer-core");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let fails = 0; const check = (c, m) => { console.log((c ? "PASS " : "FAIL ") + m); if (!c) fails++; };
const URL = "http://127.0.0.1:8766/";
(async () => {
  const b = await puppeteer.launch({ executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome", headless: true, args: ["--no-sandbox"] });
  const p = await b.newPage(); const errs = []; p.on("pageerror", (e) => errs.push(e.message));
  await p.setViewport({ width: 1280, height: 900 });
  await p.goto(URL + "#jobs", { waitUntil: "networkidle0" });
  await p.evaluate(() => localStorage.clear()); await p.reload({ waitUntil: "networkidle0" }); await p.waitForSelector(".co-head");
  const first = await p.$eval(".co", (e) => ({ key: e.dataset.co, name: e.querySelector(".nm").textContent }));
  const sel = `.co[data-co="${first.key}"]`;
  await p.click(".co-head"); await sleep(300);
  const label0 = await p.$eval(`[data-hide="${first.key}"]`, (e) => e.textContent);
  check(label0 === "Mark company as done", "expanded company shows 'Mark company as done'");
  await p.click(`[data-hide="${first.key}"]`); await sleep(300);
  const st = await p.$eval(sel, (e) => ({
    cls: e.className,
    open: e.classList.contains("open"),
    roles: [...e.querySelectorAll(".role")].map((r) => r.classList.contains("done")),
    nameColor: getComputedStyle(e.querySelector(".co-name")).color,
    pill: e.querySelector(".co-right .pill").className,
  }));
  check(/done/.test(st.cls) && st.open, `${first.name} stays in the list, expanded, greyed out`);
  check(st.roles.length > 0 && st.roles.every(Boolean), "all its roles are greyed out");
  check(/muted/.test(st.pill), "its start pill turns grey");
  const toastTxt = await p.$eval("#toast", (e) => e.textContent);
  check(/Marked .* as done.*Undo/.test(toastTxt), `toast offers Undo (${toastTxt})`);
  check((await p.$eval(`[data-hide="${first.key}"]`, (e) => e.textContent)) === "Unmark company", "link now says 'Unmark company'");
  await p.click(".toast-action"); await sleep(300);
  check(!(await p.$eval(sel, (e) => e.classList.contains("done"))), "Undo removes the grey");

  await p.click(`[data-hide="${first.key}"]`); await sleep(300);
  await p.type("#q", first.name.slice(0, 5)); await sleep(400);
  const found = await p.$$eval(".co", (els) => els.map((e) => ({ key: e.dataset.co, done: e.classList.contains("done") })));
  check(found.some((f) => f.key === first.key && f.done), "still shows up in search, greyed out");
  await p.$eval("#q", (e) => { e.value = ""; e.dispatchEvent(new Event("input", { bubbles: true })); }); await sleep(300);

  await p.reload({ waitUntil: "networkidle0" }); await p.waitForSelector(".co-head");
  check(await p.$eval(sel, (e) => e.classList.contains("done")), "still greyed after reload");
  await p.mouse.move(5, 5);
  await p.screenshot({ path: process.argv[2] || "marked.png" });

  await p.click("#filters-btn"); await sleep(150);
  await p.select("#f-hidden", "hide"); await sleep(300);
  check(!(await p.$(sel)), "optional 'Hide them' filter removes it");
  await p.select("#f-hidden", "only"); await sleep(300);
  const only = await p.$$eval(".co", (els) => els.map((e) => e.dataset.co));
  check(only.length === 1 && only[0] === first.key, "'Only these' lists just the marked company");
  await p.select("#f-hidden", "show"); await p.keyboard.press("Escape"); await sleep(300);
  check(!!(await p.$(sel)), "back to normal with the default");

  await p.evaluate(() => { location.hash = "#applications"; });
  await p.reload({ waitUntil: "networkidle0" });
  await p.evaluate(() => { window.__blobs = []; const o = URL.createObjectURL; URL.createObjectURL = (bl) => { window.__blobs.push(bl); return o(bl); }; });
  await p.click("#export"); await sleep(200);
  const exp = JSON.parse(await p.evaluate(async () => window.__blobs[0].text()));
  check(exp.tracker.companies && exp.tracker.companies[first.key] && exp.tracker.companies[first.key].hidden, "export includes marked companies");
  check(errs.length === 0, "no page errors " + errs.join("; "));
  await b.close(); console.log(fails ? `${fails} FAILED` : "ALL PASSED");
})();
