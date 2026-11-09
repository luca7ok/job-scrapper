const fs = require("fs"), vm = require("vm");
let src = fs.readFileSync(process.argv[2], "utf8").replace('const SECRET = "PUT-A-LONG-RANDOM-WORD-HERE";', 'const SECRET = "s3cret";');
const rows = [["Company", "Title", "Location", "Status", "Job Posting Link", "Contact", "Application Date", "Interview Stage"], ["Old Co", "Old role", "Cluj, Romania", "Rejected", "", "", "10/01/2026", ""]];
const formats = {};
const sheet = {
  getLastRow: () => rows.length, getLastColumn: () => Math.max(...rows.map((r) => r.length)),
  appendRow: (r) => rows.push(r), setFrozenRows() {}, getName: () => "Sheet1",
  getRange: (r, c, nr, nc) => {
    const range = {
      getValues: () => rows.slice(r - 1, r - 1 + (nr || 1)).map((x) => { const out = x.slice(c - 1, c - 1 + (nc || 1)); while (out.length < (nc || 1)) out.push(""); return out; }),
      setValue: (v) => { while (rows.length < r) rows.push([]); const row = rows[r - 1]; while (row.length < c) row.push(""); row[c - 1] = v; return range; },
      setNumberFormat: (f) => { formats[`${r},${c}`] = f; return range; },
      setFontWeight() { return range; },
    };
    return range;
  },
};
const props = {};
const ctx = {
  SpreadsheetApp: { getActiveSpreadsheet: () => ({ getSheets: () => [sheet], getSheetByName: () => sheet, insertSheet: () => sheet, getName: () => "Job applications" }) },
  PropertiesService: { getScriptProperties: () => ({ getProperty: (k) => props[k] || null, setProperty: (k, v) => { props[k] = v; } }) },
  LockService: { getScriptLock: () => ({ waitLock() {}, releaseLock() {} }) },
  ContentService: { MimeType: { JSON: "json" }, createTextOutput: (t) => ({ setMimeType: () => JSON.parse(t) }) },
  console,
};
vm.createContext(ctx);
vm.runInContext(src, ctx);
const call = (body) => ctx.doPost({ postData: { contents: JSON.stringify(body) } });
let fails = 0;
const check = (c, m) => { console.log((c ? "PASS " : "FAIL ") + m); if (!c) fails++; };

check(call({ secret: "nope", action: "ping" }).error === "wrong secret", "wrong secret rejected");
check(call({ secret: "s3cret", action: "ping" }).sheet === "Job applications › Sheet1", "ping returns sheet name");
const r1 = call({ secret: "s3cret", action: "add", rows: [
  { id: "a1", company: "Adobe", title: "2027 Intern - Security Engineer", location: "Bucharest, Romania", applied: "2026-11-09" },
  { id: "a2", company: "=HYPERLINK(\"x\")", title: "Backend Intern", location: "Amsterdam, Netherlands", applied: "2026-11-10" },
]});
check(r1.ok && r1.ids.length === 2, "two rows added");
const a = rows[2];
check(a[0] === "Adobe" && a[1] === "2027 Intern - Security Engineer" && a[2] === "Bucharest, Romania", "company/title/location in the right columns");
check([a[3], a[4], a[5], a[7]].every((v) => v === "" || v === undefined), "Status, Link, Contact, Interview Stage left empty");
check(Object.prototype.toString.call(a[6]) === "[object Date]" && a[6].getFullYear() === 2026 && a[6].getMonth() === 10 && a[6].getDate() === 9, "application date is a real date (9 Nov 2026)");
check(formats["3,7"] === "MM/dd/yyyy", "date cell formatted MM/dd/yyyy");
check(rows[3][0].startsWith("'="), "formula-looking text is neutralised");
const r2 = call({ secret: "s3cret", action: "add", rows: [{ id: "a1", company: "Adobe", title: "x", location: "y", applied: "2026-11-09" }] });
check(r2.ok && rows.length === 4, "same role is never added twice");
rows.splice(0, rows.length, ["Application Date", "Company", "Location", "Title"]);
call({ secret: "s3cret", action: "add", rows: [{ id: "b1", company: "Bolt", title: "SWE Intern", location: "Tallinn, Estonia", applied: "2026-12-01" }] });
check(rows[1][1] === "Bolt" && rows[1][2] === "Tallinn, Estonia" && rows[1][3] === "SWE Intern" && Object.prototype.toString.call(rows[1][0]) === "[object Date]", "works when columns are reordered");
rows.splice(0, rows.length,
  ["Company", "Title", "Location", "Status", "Job Posting Link", "Contact", "Application Date", "Interview Stage"],
  ["Booking.com", "Junior Software Engineer I - Summer Internship 2027", "Amsterdam", "Applied", "", "", "10/20/2026", ""],
  ["google", "software engineering intern", "Zurich", "OA", "", "", "10/22/2026", ""],
  ["Bosch GmbH", "Praktikum Softwareentwicklung (m/w/d)", "Stuttgart", "", "", "", "", ""]);
const r3 = call({ secret: "s3cret", action: "add", rows: [
  { id: "c1", company: "Booking.com", title: "Junior Software Engineer I – Summer Internship 2027", location: "Amsterdam, Netherlands", applied: "2026-11-10" },
  { id: "c2", company: "Google", title: "Software Engineering Intern, BS/MS, Summer 2027", location: "Zurich, Switzerland", applied: "2026-11-10" },
  { id: "c3", company: "Bosch", title: "Praktikum Softwareentwicklung", location: "Stuttgart, Germany", applied: "2026-11-10" },
  { id: "c4", company: "Google", title: "Site Reliability Engineering Intern", location: "Dublin, Ireland", applied: "2026-11-10" },
  { id: "c5", company: "Booking.com", title: "Data Engineer Intern", location: "Amsterdam, Netherlands", applied: "2026-11-10" },
]});
check(r3.ok && r3.ids.length === 5, "all five acknowledged");
check(JSON.stringify(r3.skipped) === JSON.stringify(["c1", "c2", "c3"]), `hand-entered rows are recognised (${r3.skipped})`);
check(rows.length === 6 && rows[4][1] === "Site Reliability Engineering Intern" && rows[5][1] === "Data Engineer Intern", "different roles at the same companies are still added");
const r4 = call({ secret: "s3cret", action: "add", rows: [{ id: "c9", company: "Google", title: "Site Reliability Engineering Intern", location: "Dublin, Ireland", applied: "2026-11-11" }] });
check(r4.skipped.length === 1 && rows.length === 6, "a row added earlier in the same session is recognised too");
rows.push(["Amazon", "2027 Software Dev Engineer Intern", "Berlin", "", "", "", "", ""]);
const r5 = call({ secret: "s3cret", action: "add", rows: [
  { id: "d1", company: "Amazon", title: "2027 Software Dev Engineer Intern", location: "Dublin, Ireland", applied: "2026-11-11" },
  { id: "d2", company: "Amazon", title: "2027 Software Dev Engineer Intern", location: "Berlin, Germany", applied: "2026-11-11" },
]});
check(JSON.stringify(r5.skipped) === JSON.stringify(["d2"]), `same title in another city is a different application (${r5.skipped})`);
rows.splice(0, rows.length, ["Company", "Title", "Location", "Status", "Job Posting Link", "Contact", "Application Date", "Interview Stage"],
  ["Old Co", "Old role", "Cluj, Romania", "Applied", "", "", "10/01/2026", ""]);
for (let i = 0; i < 984; i++) rows.push(["", "", "", false, "", "", "", "=IF(A1,1,\"\")"]);
const r6 = call({ secret: "s3cret", action: "add", rows: [
  { id: "e1", company: "Wise", title: "Software Engineering Intern", location: "Tallinn, Estonia", applied: "2026-11-12" },
  { id: "e2", company: "Bolt", title: "Backend Intern", location: "Tallinn, Estonia", applied: "2026-11-12" },
]});
check(r6.ok && rows[2][0] === "Wise" && rows[3][0] === "Bolt", `fills the first empty rows (3 and 4), not row ${rows.length + 1}`);
check(rows[2][3] === false && rows[2][7] === "=IF(A1,1,\"\")", "leaves your checkboxes and formulas in that row untouched");
check(rows.length === 986, "no rows appended at the bottom");
console.log(fails ? `${fails} FAILED` : "ALL PASSED");
