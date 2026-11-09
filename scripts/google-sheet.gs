const SECRET = "PUT-A-LONG-RANDOM-WORD-HERE";
const SHEET_NAME = "";
const HEADERS = ["Company", "Title", "Location", "Status", "Job Posting Link", "Contact", "Application Date", "Interview Stage"];
const DATE_FORMAT = "MM/dd/yyyy";

function doPost(e) {
  let data;
  try {
    data = JSON.parse(e.postData.contents);
  } catch (err) {
    return reply({ ok: false, error: "bad request" });
  }
  if (SECRET === "PUT-A-LONG-RANDOM-WORD-HERE") return reply({ ok: false, error: "set SECRET in the script first" });
  if (!data || data.secret !== SECRET) return reply({ ok: false, error: "wrong secret" });

  const book = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = SHEET_NAME ? book.getSheetByName(SHEET_NAME) || book.insertSheet(SHEET_NAME) : book.getSheets()[0];
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(HEADERS);
    sheet.setFrozenRows(1);
    sheet.getRange(1, 1, 1, HEADERS.length).setFontWeight("bold");
  }
  if (data.action === "ping") return reply({ ok: true, sheet: book.getName() + " › " + sheet.getName() });

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const cols = columns(sheet);
    const missing = ["company", "title", "location", "application date"].filter((h) => !cols[h]);
    if (missing.length) return reply({ ok: false, error: "missing column(s): " + missing.join(", ") });
    const props = PropertiesService.getScriptProperties();
    const width = sheet.getLastColumn();
    const existing = existingRows(sheet, cols);
    const done = [];
    const skipped = [];
    for (const r of data.rows || []) {
      if (!r || !r.id) continue;
      const key = "sent_" + r.id;
      if (props.getProperty(key)) {
        done.push(String(r.id));
        continue;
      }
      if (alreadyListed(existing, r.company, r.title, r.location)) {
        props.setProperty(key, "1");
        done.push(String(r.id));
        skipped.push(String(r.id));
        continue;
      }
      const row = new Array(width).fill("");
      row[cols["company"] - 1] = cell(r.company);
      row[cols["title"] - 1] = cell(r.title);
      row[cols["location"] - 1] = cell(r.location);
      row[cols["application date"] - 1] = toDate(r.applied);
      sheet.appendRow(row);
      sheet.getRange(sheet.getLastRow(), cols["application date"]).setNumberFormat(DATE_FORMAT);
      props.setProperty(key, "1");
      existing.push({ company: norm(r.company), title: norm(r.title), location: norm(r.location) });
      done.push(String(r.id));
    }
    return reply({ ok: true, ids: done, skipped: skipped });
  } finally {
    lock.releaseLock();
  }
}

function columns(sheet) {
  const header = sheet.getRange(1, 1, 1, Math.max(sheet.getLastColumn(), 1)).getValues()[0];
  const map = {};
  header.forEach((name, i) => {
    const key = String(name).trim().toLowerCase();
    if (key && !map[key]) map[key] = i + 1;
  });
  return map;
}

function existingRows(sheet, cols) {
  const last = sheet.getLastRow();
  if (last < 2) return [];
  const width = sheet.getLastColumn();
  return sheet.getRange(2, 1, last - 1, width).getValues().map((row) => ({
    company: norm(row[cols["company"] - 1]),
    title: norm(row[cols["title"] - 1]),
    location: norm(row[cols["location"] - 1]),
  })).filter((r) => r.company);
}

function norm(value) {
  return String(value === null || value === undefined ? "" : value)
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\((m\/w\/d|f\/m\/d|m\/f\/d|w\/m\/d|m\/f\/x|f\/m\/x|h\/f|f\/h|all genders)\)/g, " ")
    .replace(/\b(gmbh|ag|se|sa|ltd|inc|llc|plc|bv|nv|spa|sas|srl|ab|as|oy|group)\b\.?/g, " ")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function sameCity(rowLocation, location) {
  const city = norm(String(location || "").split(",")[0]);
  if (!rowLocation || !city) return true;
  const rowCity = rowLocation.split(" ")[0];
  return rowLocation.indexOf(city) !== -1 || city.indexOf(rowCity) !== -1;
}

function alreadyListed(existing, company, title, location) {
  const c = norm(company);
  const t = norm(title);
  if (!c) return false;
  return existing.some((row) => {
    if (!sameCity(row.location, location)) return false;
    if (row.company !== c && !(row.company.length >= 3 && (c.indexOf(row.company) === 0 || row.company.indexOf(c) === 0))) return false;
    if (!row.title || !t) return false;
    if (row.title === t) return true;
    const shorter = row.title.length < t.length ? row.title : t;
    const longer = shorter === t ? row.title : t;
    return shorter.length >= 8 && longer.indexOf(shorter) !== -1;
  });
}

function toDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ""));
  return m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : new Date();
}

function cell(value) {
  const s = value === null || value === undefined ? "" : String(value);
  return /^[=+\-@]/.test(s) ? "'" + s : s;
}

function reply(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
