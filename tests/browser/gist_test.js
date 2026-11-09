const puppeteer = require("puppeteer-core");

const URL = process.argv[2] || "http://127.0.0.1:8766/";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let failures = 0;
const check = (cond, msg) => { console.log(`${cond ? "PASS" : "FAIL"} ${msg}`); if (!cond) failures++; };

const gists = {};
let nextId = 1;
const calls = [];

async function mock(page) {
  await page.setRequestInterception(true);
  page.on("request", (req) => {
    const u = new globalThis.URL(req.url());
    if (u.host !== "api.github.com") return req.continue();
    const auth = req.headers()["authorization"];
    calls.push(`${req.method()} ${u.pathname}`);
    const json = (status, body) => req.respond({ status, contentType: "application/json", headers: { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "*" }, body: JSON.stringify(body) });
    if (req.method() === "OPTIONS") return json(204, {});
    if (auth !== "Bearer good-token") return json(401, { message: "Bad credentials" });
    if (u.pathname === "/gists" && req.method() === "GET") return json(200, Object.values(gists));
    if (u.pathname === "/gists" && req.method() === "POST") {
      const body = JSON.parse(req.postData());
      const id = "g" + nextId++;
      gists[id] = { id, public: body.public, files: Object.fromEntries(Object.entries(body.files).map(([k, v]) => [k, { content: v.content }])) };
      return json(201, gists[id]);
    }
    const m = u.pathname.match(/^\/gists\/(\w+)$/);
    if (m && gists[m[1]]) {
      if (req.method() === "GET") return json(200, gists[m[1]]);
      if (req.method() === "PATCH") {
        const body = JSON.parse(req.postData());
        for (const [k, v] of Object.entries(body.files)) gists[m[1]].files[k] = { content: v.content };
        return json(200, gists[m[1]]);
      }
    }
    return json(404, {});
  });
}

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome", headless: true, args: ["--no-sandbox"] });
  const ctxA = await browser.createBrowserContext();
  const ctxB = await browser.createBrowserContext();
  const a = await ctxA.newPage();
  const b = await ctxB.newPage();
  for (const p of [a, b]) { await mock(p); p.on("dialog", (d) => d.accept()); }

  await a.goto(URL + "#jobs", { waitUntil: "networkidle0" });
  await a.waitForSelector(".co-head");
  await a.click(".co-head");
  await sleep(300);
  const id1 = await a.$eval("[data-track]", (e) => e.dataset.track);
  await a.select(`[data-track="${id1}"]`, "saved");

  await a.goto(URL + "#applications", { waitUntil: "networkidle0" });
  await a.type("#gist-token", "bad-token");
  await a.click("#gist-connect");
  await sleep(400);
  check(await a.$eval("#sync-on", (e) => e.hidden), "bad token is rejected and not stored");
  check((await a.evaluate(() => localStorage.getItem("tracker.gist.v1"))) === null, "bad token not persisted");

  await a.$eval("#gist-token", (e) => (e.value = ""));
  await a.type("#gist-token", "good-token");
  await a.click("#gist-connect");
  await sleep(600);
  const ids = Object.keys(gists);
  check(ids.length === 1 && gists[ids[0]].public === false, "private gist created on first connect");
  const content = JSON.parse(gists[ids[0]].files["eu-swe-2027-tracker.json"].content);
  check(content.items[id1] && content.items[id1].status === "saved", "local tracker pushed to gist");
  check(!(await a.$eval("#sync-on", (e) => e.hidden)), "UI shows connected state");

  await b.goto(URL + "#applications", { waitUntil: "networkidle0" });
  await b.type("#gist-token", "good-token");
  await b.click("#gist-connect");
  await sleep(600);
  check(Object.keys(gists).length === 1, "second device reuses the existing gist");
  const bItems = JSON.parse(await b.evaluate(() => localStorage.getItem("tracker.v1"))).items;
  check(bItems[id1] && bItems[id1].status === "saved", "second device pulls the tracker");

  await b.goto(URL + "#jobs", { waitUntil: "networkidle0" });
  await b.waitForSelector(".co-head");
  const heads = await b.$$(".co-head");
  await heads[1].click();
  await sleep(300);
  const id2 = await b.$$eval(".co.open [data-track]", (els) => els[0].dataset.track);
  await b.select(`[data-track="${id2}"]`, "applied");
  await sleep(3600);
  const after = JSON.parse(gists[ids[0]].files["eu-swe-2027-tracker.json"].content);
  check(after.items[id2] && after.items[id2].status === "applied" && after.items[id1].status === "saved", "change on device B auto-syncs and keeps device A's item");

  await a.reload({ waitUntil: "networkidle0" });
  await sleep(800);
  const aItems = JSON.parse(await a.evaluate(() => localStorage.getItem("tracker.v1"))).items;
  check(aItems[id2] && aItems[id2].status === "applied", "device A picks up device B's change on load");
  const rows = await a.$$eval(".app", (e) => e.length);
  check(rows === 2, `device A shows both applications (${rows})`);

  await a.evaluate(() => { const t = JSON.parse(localStorage.getItem("tracker.v1")); t.companies = { acme: { hidden: true, name: "Acme", u: Date.now() } }; localStorage.setItem("tracker.v1", JSON.stringify(t)); });
  await a.reload({ waitUntil: "networkidle0" }); await sleep(300);
  await a.click("#gist-sync"); await sleep(800);
  const g2 = JSON.parse(gists[ids[0]].files["eu-swe-2027-tracker.json"].content);
  check(g2.companies && g2.companies.acme && g2.companies.acme.hidden, "hidden companies sync to the gist");
  await b.reload({ waitUntil: "networkidle0" }); await sleep(800);
  const bt = JSON.parse(await b.evaluate(() => localStorage.getItem("tracker.v1")));
  check(bt.companies && bt.companies.acme && bt.companies.acme.hidden, "and reach the second device");
  await a.click("#gist-disconnect");
  check((await a.evaluate(() => localStorage.getItem("tracker.gist.v1"))) === null, "disconnect forgets the token");
  console.log("calls:", calls.join(", "));
  await browser.close();
  console.log(failures ? `${failures} FAILED` : "ALL PASSED");
  process.exit(failures ? 1 : 0);
})();
