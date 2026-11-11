(() => {
  "use strict";

  const KEYS = { tracker: "tracker.v1", filters: "filters.v1", gist: "tracker.gist.v1", sheet: "tracker.sheet.v1" };
  const PAGE = 40;
  const GIST_FILE = "eu-swe-2027-tracker.json";

  const COUNTRY = {
    AT: "Austria", BE: "Belgium", BG: "Bulgaria", HR: "Croatia", CY: "Cyprus", CZ: "Czechia",
    DK: "Denmark", EE: "Estonia", FI: "Finland", FR: "France", DE: "Germany", GR: "Greece",
    HU: "Hungary", IE: "Ireland", IT: "Italy", LV: "Latvia", LT: "Lithuania", LU: "Luxembourg",
    MT: "Malta", NL: "Netherlands", PL: "Poland", PT: "Portugal", RO: "Romania", SK: "Slovakia",
    SI: "Slovenia", ES: "Spain", SE: "Sweden", IS: "Iceland", LI: "Liechtenstein", NO: "Norway",
    CH: "Switzerland", GB: "United Kingdom", RS: "Serbia", MK: "North Macedonia",
    BA: "Bosnia and Herzegovina", ME: "Montenegro", AL: "Albania", XK: "Kosovo", UA: "Ukraine",
    MD: "Moldova", TR: "Türkiye", EU: "Europe (remote)",
  };

  const STATUSES = [
    ["", "—"], ["saved", "Saved"], ["applied", "Applied"], ["logged", "Already applied"], ["oa", "OA"], ["interview", "Interview"],
    ["offer", "Offer"], ["rejected", "Rejected"], ["withdrawn", "Withdrawn"],
  ];
  const STATUS_LABEL = Object.fromEntries(STATUSES);
  const STATUS_ORDER = { offer: 0, interview: 1, oa: 2, applied: 3, logged: 3, saved: 4, rejected: 5, withdrawn: 6 };
  const BUCKET_RANK = { july: 3, summer: 2, other: 1, none: 0 };
  const DONE = new Set(["applied", "logged", "oa", "interview", "offer", "rejected", "withdrawn"]);
  const SHEET_STATUSES = new Set(["applied", "oa", "interview", "offer"]);
  const COUNTRY_ALIASES = ["uk", "u.k.", "great britain", "england", "scotland", "wales", "northern ireland", "the netherlands", "holland", "deutschland", "czech republic", "turkey", "espana", "italia", "polska", "osterreich", "schweiz", "suisse", "belgique", "romania", "worldwide", "europe", "emea", "eu"];
  const DEFAULT_FILTERS = { q: "", kind: "all", country: "noUK", size: "all", start: "any", status: "open", mine: "any", hidden: "show" };

  const $ = (sel) => document.querySelector(sel);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fold = (s) => String(s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const normCompany = (s) => fold(s).replace(/&/g, " and ").replace(/\(.*?\)/g, " ").replace(/\b(gmbh|ag|se|sa|ltd|limited|inc|llc|plc|bv|nv|spa|sas|srl|ab|as|oy|group|holding|co|corp|corporation|company)\b\.?/g, " ").replace(/[^a-z0-9]+/g, "");

  const store = {
    get(key, fallback) {
      try {
        const raw = localStorage.getItem(key);
        return raw == null ? fallback : JSON.parse(raw);
      } catch (e) {
        return fallback;
      }
    },
    set(key, value) {
      try {
        localStorage.setItem(key, JSON.stringify(value));
        return true;
      } catch (e) {
        return false;
      }
    },
    remove(key) {
      try { localStorage.removeItem(key); } catch (e) { /* storage unavailable */ }
    },
  };

  const fmtDate = (iso) => {
    if (!iso) return "";
    const d = new Date(iso.length <= 10 ? iso + "T00:00:00Z" : iso);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
  };
  const todayIso = () => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  };

  const S = {
    data: null,
    roles: [],
    byId: new Map(),
    filters: { ...DEFAULT_FILTERS, ...store.get(KEYS.filters, {}) },
    tracker: loadTracker(),
    shown: PAGE,
    expanded: new Set(),
    openNotes: new Set(),
    groups: [],
  };

  function loadTracker() {
    const t = store.get(KEYS.tracker, null);
    if (t && typeof t === "object" && t.items && typeof t.items === "object") return { v: 1, items: t.items, companies: t.companies && typeof t.companies === "object" ? t.companies : {} };
    return { v: 1, items: {}, companies: {} };
  }

  function saveTracker() {
    if (!store.set(KEYS.tracker, S.tracker)) toast("Couldn't save: browser storage is unavailable.");
    gist.schedule();
  }

  function track(id) {
    const it = S.tracker.items[id];
    return it && it.status ? it : null;
  }

  function isDone(id) {
    const t = track(id);
    return !!(t && DONE.has(t.status));
  }

  function allDone(g) {
    return g.roles.length > 0 && g.roles.every((r) => isDone(r.id));
  }

  function titleCase(s) {
    return s === s.toLowerCase() ? s.replace(/(^|[\s-])(\p{L})/gu, (m, a, b) => a + b.toUpperCase()) : s;
  }

  function cityCountry(locations, countries) {
    const code = (countries || [])[0];
    const country = code === "EU" ? "Europe" : code ? COUNTRY[code] || code : "";
    const notCountry = new Set([...Object.values(COUNTRY), ...COUNTRY_ALIASES, ...Object.keys(COUNTRY)].map((x) => fold(x)));
    let chunk = String(locations || "").split(";")[0].replace(/\s*\+\s*\d+\s*(more)?\s*$/i, "").trim();
    let remote = false;
    if (/^remote\b/i.test(chunk)) {
      remote = true;
      chunk = chunk.replace(/^remote\s*(-|–|in|,|:)?\s*/i, "");
    }
    const parts = chunk.split(",").map((x) => {
      let part = x.trim();
      const stripped = part.replace(/\s*[-–(]\s*(remote|hybrid)\)?$/i, "").replace(/^(remote|hybrid)\s*[-–:]\s*/i, "");
      if (stripped !== part) { remote = remote || /remote/i.test(part); part = stripped.trim(); }
      return part;
    });
    const city = parts.find((x) => x && !notCountry.has(fold(x)) && !/^(remote|hybrid|on-?site)$/i.test(x));
    const place = city ? titleCase(city) : remote ? "Remote" : "";
    if (place && country) return `${place}, ${country}`;
    return place || country || "";
  }

  function setTrack(id, patch) {
    const role = S.byId.get(id);
    const prev = S.tracker.items[id] || {};
    const next = { ...prev, ...patch, u: Date.now() };
    if (patch.status === "applied" && !prev.applied) next.applied = todayIso();
    if (role) next.snap = { c: role.company, t: role.title, url: role.url, loc: role.locations };
    S.tracker.items[id] = next;
    saveTracker();
  }

  let toastTimer = null;
  function toast(msg, actionLabel, onAction) {
    const el = $("#toast");
    el.textContent = msg;
    if (actionLabel) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "toast-action";
      btn.textContent = actionLabel;
      btn.addEventListener("click", () => { el.hidden = true; onAction(); });
      el.append(" ", btn);
    }
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.hidden = true; }, actionLabel ? 6000 : 3200);
  }

  function isHidden(key) {
    const c = (S.tracker.companies || {})[key];
    return !!(c && c.hidden);
  }

  function setHidden(key, company, hidden) {
    S.tracker.companies = S.tracker.companies || {};
    S.tracker.companies[key] = { hidden, name: company, u: Date.now() };
    saveTracker();
  }

  function hiddenCount() {
    return Object.values(S.tracker.companies || {}).filter((c) => c && c.hidden).length;
  }

  function saveFilters() {
    store.set(KEYS.filters, S.filters);
  }

  function activeFilterCount() {
    let n = 0;
    for (const k of ["kind", "country", "size", "start", "status", "mine", "hidden"]) {
      if (S.filters[k] !== DEFAULT_FILTERS[k]) n++;
    }
    return n;
  }

  function roleMatches(r, f) {
    if (f.kind !== "all" && r.kind !== f.kind) return false;
    if (f.country === "noUK") {
      if (r.countries.length && !r.countries.some((c) => c !== "GB")) return false;
    } else if (f.country !== "all" && !r.countries.includes(f.country)) return false;
    if (f.size === "midsize" && !r.midsize) return false;
    if (f.start === "july" && r.start_bucket !== "july") return false;
    if (f.start === "summer" && r.start_bucket !== "july" && r.start_bucket !== "summer") return false;
    if (f.start === "stated" && r.start_bucket === "none") return false;
    if (f.status === "open" && r.status !== "open") return false;
    if (f.status === "new" && !(r.status === "open" && r.is_new)) return false;
    if (f.status === "expected" && r.status !== "expected") return false;
    if (f.status === "closed" && r.status !== "closed") return false;
    if (f.mine !== "any") {
      const t = track(r.id);
      if (f.mine === "none" ? t : !t || t.status !== f.mine) return false;
    }
    if (f.hidden === "hide" && isHidden(r._co)) return false;
    if (f.hidden === "only" && !isHidden(r._co)) return false;
    if (f.q) {
      const terms = fold(f.q).split(/\s+/).filter(Boolean);
      for (const term of terms) if (!r._hay.includes(term)) return false;
    }
    return true;
  }

  function pillFor(bucket, label, muted) {
    const m = muted ? " muted" : "";
    if (bucket === "expected") return `<span class="pill expected${m}">Not open yet</span>`;
    if (bucket === "closed") return `<span class="pill closed">Closed</span>`;
    const text = { july: "July", summer: "Summer", other: "2027", none: "Not stated" }[bucket] || "Not stated";
    const title = label ? ` title="${esc(label)}"` : "";
    return `<span class="pill ${esc(bucket)}${m}"${title}>${text}</span>`;
  }

  function groupRoles(list) {
    const map = new Map();
    for (const r of list) {
      const k = r._co;
      let g = map.get(k);
      if (!g) {
        g = { key: k, company: r.company, roles: [], midsize: false, isNew: false, best: -1, bestRole: null, kinds: new Set(), countries: new Set() };
        map.set(k, g);
      }
      g.roles.push(r);
      g.midsize = g.midsize || r.midsize;
      g.isNew = g.isNew || r.is_new;
      g.kinds.add(r.kind);
      r.countries.forEach((c) => g.countries.add(c));
      const rank = r.status === "open" ? BUCKET_RANK[r.start_bucket] ?? 0 : -1;
      if (rank > g.best || !g.bestRole) { g.best = rank; g.bestRole = r; }
    }
    const groups = [...map.values()];
    for (const g of groups) {
      g.roles.sort((a, b) => (BUCKET_RANK[b.start_bucket] - BUCKET_RANK[a.start_bucket]) || (b.is_new - a.is_new) || a.title.localeCompare(b.title));
      const allExpected = g.roles.every((r) => r.status === "expected");
      const allClosed = g.roles.every((r) => r.status === "closed");
      g.pill = allExpected ? "expected" : allClosed ? "closed" : g.bestRole.start_bucket;
      g.pillLabel = allExpected || allClosed ? "" : g.bestRole.start_label;
      g.continental = [...g.countries].some((c) => c !== "GB");
    }
    groups.sort((a, b) => (b.best - a.best) || (b.isNew - a.isNew) || (b.continental - a.continental) || (b.midsize - a.midsize) || a.company.localeCompare(b.company));
    return groups;
  }

  function countryList(codes) {
    const names = [...codes].map((c) => (c === "GB" ? "UK" : c === "EU" ? "Europe" : COUNTRY[c] || c));
    if (names.length > 4) return names.slice(0, 4).join(", ") + ` +${names.length - 4}`;
    return names.join(", ");
  }

  function trackControl(r) {
    const t = track(r.id);
    const st = t ? t.status : "";
    const label = st ? STATUS_LABEL[st] : "Track";
    const opts = STATUSES.map(([v, l]) => `<option value="${v}"${v === st ? " selected" : ""}>${l}</option>`).join("");
    return `<span class="track${st ? " st-" + st : ""}"><span class="val" aria-hidden="true">${esc(label)}</span><select data-track="${esc(r.id)}" aria-label="Application status for ${esc(r.title)} at ${esc(r.company)}">${opts}</select></span>`;
  }

  function roleHtml(r, mixedKinds, companyDone) {
    const t = track(r.id);
    const bits = [];
    if (r.locations) bits.push(esc(r.locations.length > 90 ? r.locations.slice(0, 88) + "…" : r.locations));
    else if (r.countries.length) bits.push(esc(countryList(r.countries)));
    bits.push(esc(r.start_label));
    if (mixedKinds) bits.push(esc(r.kind));
    if (r.status === "closed") bits.push(`closed ${esc(fmtDate(r.closed_on))}`);
    else if (r.posted) bits.push(`posted ${esc(fmtDate(r.posted))}`);
    else if (r.first_seen) bits.push(`first seen ${esc(fmtDate(r.first_seen))}`);
    bits.push(esc((r.sources || [r.source]).join(", ")));
    const noteOpen = S.openNotes.has(r.id);
    const noteBtn = t ? `<button type="button" class="link notebtn" data-note="${esc(r.id)}" aria-expanded="${noteOpen}">${t.notes ? "Notes" : "Add note"}</button>` : "";
    const notes = t && noteOpen ? `<div class="role-notes"><label class="sr-only" for="n-${esc(r.id)}">Notes</label><textarea id="n-${esc(r.id)}" data-notes="${esc(r.id)}" placeholder="Notes: referral, deadlines, contacts…">${esc(t.notes || "")}</textarea></div>` : "";
    const cls = ((t && DONE.has(t.status)) || companyDone ? " done" : "") + (t && t.status === "rejected" ? " rejected" : "");
    const newDot = r.is_new ? `<span class="sr-only">New. </span>` : "";
    return `<div class="role${cls}">
      <div>${newDot}<a class="role-title" href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)} <span class="arrow" aria-hidden="true">↗</span></a></div>
      <div class="role-ctl">${trackControl(r)}${noteBtn}</div>
      <div class="role-meta">${bits.join(" · ")}</div>
      ${r.note ? `<div class="role-note">${esc(r.note)}</div>` : ""}
      ${notes}
    </div>`;
  }

  function rolesHtml(g) {
    const marked = isHidden(g.key);
    const action = `<div class="co-actions"><button type="button" class="link" data-hide="${esc(g.key)}" data-company="${esc(g.company)}">${marked ? "Unmark company" : "Mark company as done"}</button></div>`;
    return g.roles.map((r) => roleHtml(r, g.kinds.size > 1, marked)).join("") + action;
  }

  function companyHtml(g) {
    const open = S.expanded.has(g.key);
    const id = "co-" + g.key;
    const n = g.roles.length;
    const kinds = [...g.kinds].join(", ");
    const done = allDone(g);
    const hiddenCo = isHidden(g.key);
    return `<div class="co${open ? " open" : ""}${done || hiddenCo ? " done" : ""}${hiddenCo ? " is-hidden" : ""}" data-co="${esc(g.key)}">
      <button type="button" class="co-head" aria-expanded="${open}" aria-controls="${esc(id)}">
        <span class="co-name">${g.isNew ? `<span class="dot" aria-hidden="true"></span><span class="sr-only">New roles: </span>` : ""}<span class="nm">${esc(g.company)}</span>${g.midsize ? `<span class="tag">mid-size</span>` : ""}</span>
        <span class="co-right">${pillFor(g.pill, g.pillLabel, done || hiddenCo)}<span class="co-count" aria-label="${n} role${n === 1 ? "" : "s"}">${n}</span></span>
        <span class="co-sub">${esc(kinds)} · ${esc(countryList(g.countries))}</span>
      </button>
      <div class="roles" id="${esc(id)}"><div class="roles-inner">${open ? rolesHtml(g) : ""}</div></div>
    </div>`;
  }

  function renderStats() {
    const s = S.data.stats;
    const parts = [
      `${s.companies} companies`,
      `${s.roles} roles`,
      `${s.outside_uk} outside UK`,
      `${s.midsize_eu} mid-size EU`,
      `${s.new_week} new this week`,
      `updated ${fmtDate(S.data.generated_at)}`,
    ];
    $("#stats").innerHTML = parts.map((p) => `<span class="nw">${esc(p)}</span>`).join(" · ");
  }

  function renderChips() {
    const f = S.filters;
    for (const btn of document.querySelectorAll("[data-chip]")) {
      const [k, v] = btn.dataset.chip.split(":");
      btn.setAttribute("aria-pressed", String(f[k] === v));
    }
    const n = activeFilterCount();
    const c = $("#filters-count");
    c.hidden = n === 0;
    c.textContent = n;
    $("#filters-btn").setAttribute("aria-label", n ? `Filters, ${n} active` : "Filters");
    for (const sel of document.querySelectorAll("[data-filter]")) sel.value = f[sel.dataset.filter];
  }

  function renderJobs() {
    const visible = S.roles.filter((r) => roleMatches(r, S.filters));
    S.groups = groupRoles(visible);
    const list = $("#list");
    const slice = S.groups.slice(0, S.shown);
    if (!slice.length) {
      list.innerHTML = `<p class="empty">No roles match these filters. <button type="button" class="link" id="empty-reset">Reset filters</button></p>`;
    } else {
      list.innerHTML = slice.map(companyHtml).join("");
    }
    const more = $("#more");
    more.hidden = S.groups.length <= S.shown;
    more.textContent = `Show more (${S.groups.length - S.shown} companies)`;
    const nRoles = visible.length;
    const nHidden = hiddenCount();
    $("#resultline").textContent = `${S.groups.length} compan${S.groups.length === 1 ? "y" : "ies"} · ${nRoles} role${nRoles === 1 ? "" : "s"}` + (nHidden && S.filters.hidden === "hide" ? ` · ${nHidden} marked done and hidden` : "");
    renderChips();
  }

  function rerenderCompany(key) {
    const g = S.groups.find((x) => x.key === key);
    const el = document.querySelector(`.co[data-co="${CSS.escape(key)}"]`);
    if (!g || !el) return;
    const hiddenCo = isHidden(g.key);
    const done = allDone(g) || hiddenCo;
    el.classList.toggle("done", done);
    el.classList.toggle("is-hidden", hiddenCo);
    const pill = el.querySelector(".co-right .pill");
    if (pill) pill.outerHTML = pillFor(g.pill, g.pillLabel, done);
    const inner = el.querySelector(".roles-inner");
    inner.innerHTML = S.expanded.has(key) ? rolesHtml(g) : "";
  }

  function toggleCompany(key) {
    const el = document.querySelector(`.co[data-co="${CSS.escape(key)}"]`);
    if (!el) return;
    const head = el.querySelector(".co-head");
    if (S.expanded.has(key)) {
      S.expanded.delete(key);
      el.classList.remove("open");
      head.setAttribute("aria-expanded", "false");
      setTimeout(() => { if (!S.expanded.has(key)) el.querySelector(".roles-inner").innerHTML = ""; }, 160);
    } else {
      S.expanded.add(key);
      rerenderCompany(key);
      requestAnimationFrame(() => el.classList.add("open"));
      head.setAttribute("aria-expanded", "true");
    }
  }

  function renderWatchlist() {
    const items = S.data.watchlist || [];
    const html = items.map((w) => {
      const pill = w.open_now ? `<span class="pill opennow">Open now</span>` : `<span class="pill expected">Not open yet</span>`;
      const meta = [];
      if (w.type === "expected" && w.title) meta.push(esc(w.title));
      if (w.start && w.start !== "Not stated") meta.push(esc(w.start));
      if (w.note) meta.push(esc(w.note));
      const links = [];
      if (w.url) links.push(`<a href="${esc(w.url)}" target="_blank" rel="noopener">${w.type === "career_site" ? "Career site" : "Last posting"} ↗</a>`);
      if (w.open_now) links.push(`<button type="button" class="link" data-show-company="${esc(w.company)}">See ${w.open_roles} role${w.open_roles === 1 ? "" : "s"}</button>`);
      if (w.last_checked) links.push(`last checked ${esc(fmtDate(w.last_checked))}`);
      const progs = (w.programmes || []).map((p) => `<div class="prog meta">${esc(p.title)}${p.start && p.start !== "Not stated" ? " · " + esc(p.start) : ""}</div>`).join("");
      return `<div class="watch">
        <span class="co-name"><span class="nm">${esc(w.company)}</span>${w.midsize ? `<span class="tag">mid-size</span>` : ""}</span>
        <span>${pill}</span>
        ${meta.length ? `<p class="meta">${meta.join(" · ")}</p>` : ""}
        ${progs}
        <p class="meta">${links.join(" · ")}</p>
      </div>`;
    }).join("");
    $("#watchlist").innerHTML = html || `<p class="empty">The watchlist is empty.</p>`;
  }

  function renderApps() {
    const entries = Object.entries(S.tracker.items).filter(([, t]) => t && t.status);
    const counts = {};
    for (const [, t] of entries) counts[t.status] = (counts[t.status] || 0) + 1;
    const countLine = STATUSES.filter(([v]) => v && counts[v]).map(([v, l]) => `${counts[v]} ${l.toLowerCase()}`).join(" · ");
    $("#apps-counts").textContent = entries.length ? `${entries.length} tracked · ${countLine}` : "Nothing tracked yet. Use the status pill next to any role to start.";
    entries.sort(([, a], [, b]) => (STATUS_ORDER[a.status] - STATUS_ORDER[b.status]) || String(b.applied || "").localeCompare(String(a.applied || "")) || (b.u || 0) - (a.u || 0));
    $("#apps").innerHTML = entries.map(([id, t]) => {
      const r = S.byId.get(id);
      const snap = t.snap || {};
      const company = r ? r.company : snap.c || "Unknown company";
      const title = r ? r.title : snap.t || "Role no longer listed";
      const url = r ? r.url : snap.url || "#";
      const gone = !r || r.status === "closed";
      const stub = { id, title, company };
      const meta = [];
      if (r && r.locations) meta.push(esc(r.locations.slice(0, 80)));
      else if (snap.loc) meta.push(esc(snap.loc.slice(0, 80)));
      if (r) meta.push(esc(r.start_label));
      if (gone) meta.push(r ? `closed ${esc(fmtDate(r.closed_on))}` : "no longer listed");
      return `<div class="app${gone ? " gone" : ""}${t.status === "rejected" ? " rejected" : ""}">
        <div><strong>${esc(company)}</strong><br><a class="role-title" href="${esc(url)}" target="_blank" rel="noopener">${esc(title)} <span class="arrow" aria-hidden="true">↗</span></a></div>
        <div>${trackControl(stub)}</div>
        <div class="role-meta">${meta.join(" · ")}</div>
        <div class="app-fields">
          <label>Applied <input type="date" value="${esc(t.applied || "")}" data-applied="${esc(id)}" aria-label="Date applied for ${esc(title)}"></label>
          <input type="text" value="${esc(t.notes || "")}" placeholder="Notes" data-notes="${esc(id)}" aria-label="Notes for ${esc(title)}">
        </div>
      </div>`;
    }).join("");
    renderSync();
    renderSheet();
  }

  function render() {
    renderJobs();
    if (!$("#view-watchlist").hidden) renderWatchlist();
    if (!$("#view-applications").hidden) renderApps();
  }

  function setTab(tab) {
    const valid = ["jobs", "watchlist", "applications"];
    if (!valid.includes(tab)) tab = "jobs";
    for (const t of valid) $(`#view-${t}`).hidden = t !== tab;
    for (const a of document.querySelectorAll("[data-tab]")) {
      if (a.dataset.tab === tab) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    }
    if (!S.data) return;
    if (tab === "watchlist") renderWatchlist();
    if (tab === "applications") renderApps();
  }

  function populateSelects() {
    const counts = {};
    for (const r of S.roles) if (r.status === "open") for (const c of r.countries) counts[c] = (counts[c] || 0) + 1;
    const codes = Object.keys(counts).sort((a, b) => (COUNTRY[a] || a).localeCompare(COUNTRY[b] || b));
    $("#f-country").innerHTML = [`<option value="noUK">All except UK</option>`, `<option value="all">All countries</option>`]
      .concat(codes.map((c) => `<option value="${c}">${esc(COUNTRY[c] || c)} (${counts[c]})</option>`)).join("");
    if (S.filters.country !== "noUK" && S.filters.country !== "all" && !counts[S.filters.country]) S.filters.country = "noUK";
    $("#f-mine").innerHTML = [`<option value="any">Any</option>`, `<option value="none">Not applied</option>`]
      .concat(STATUSES.filter(([v]) => v).map(([v, l]) => `<option value="${v}">${l}</option>`)).join("");
  }

  function openSheet(open) {
    const sheet = $("#filters-sheet");
    sheet.hidden = !open;
    $("#sheet-backdrop").hidden = !open;
    $("#filters-btn").setAttribute("aria-expanded", String(open));
    if (open) $("#f-kind").focus();
    else $("#filters-btn").focus();
  }

  function setFilter(k, v) {
    S.filters[k] = v;
    S.shown = PAGE;
    saveFilters();
    renderJobs();
  }

  function bind() {
    let qTimer = null;
    $("#q").value = S.filters.q;
    $("#q").addEventListener("input", (e) => {
      clearTimeout(qTimer);
      qTimer = setTimeout(() => setFilter("q", e.target.value.trim()), 120);
    });

    $("#chips").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-chip]");
      if (!btn) return;
      const [k, v] = btn.dataset.chip.split(":");
      const off = { start: "any", status: "open", size: "all" }[k];
      setFilter(k, S.filters[k] === v && v !== "any" ? off : v);
    });

    $("#filters-btn").addEventListener("click", () => openSheet($("#filters-sheet").hidden));
    $("#filters-done").addEventListener("click", () => openSheet(false));
    $("#sheet-backdrop").addEventListener("click", () => openSheet(false));
    $("#filters-reset").addEventListener("click", () => {
      const q = S.filters.q;
      S.filters = { ...DEFAULT_FILTERS, q };
      saveFilters();
      renderJobs();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !$("#filters-sheet").hidden) openSheet(false);
    });
    for (const sel of document.querySelectorAll("[data-filter]")) {
      sel.addEventListener("change", () => setFilter(sel.dataset.filter, sel.value));
    }

    $("#list").addEventListener("click", (e) => {
      const hb = e.target.closest("[data-hide]");
      if (hb) {
        const key = hb.dataset.hide;
        const name = hb.dataset.company;
        const hide = !isHidden(key);
        setHidden(key, name, hide);
        if (hide && S.filters.hidden === "hide") S.expanded.delete(key);
        renderJobs();
        if (hide) toast(`Marked ${name} as done.`, "Undo", () => { setHidden(key, name, false); renderJobs(); });
        return;
      }
      const head = e.target.closest(".co-head");
      if (head) { toggleCompany(head.parentElement.dataset.co); return; }
      const nb = e.target.closest("[data-note]");
      if (nb) {
        const id = nb.dataset.note;
        if (S.openNotes.has(id)) S.openNotes.delete(id); else S.openNotes.add(id);
        const g = S.groups.find((x) => x.roles.some((r) => r.id === id));
        if (g) rerenderCompany(g.key);
        if (S.openNotes.has(id)) { const ta = document.getElementById("n-" + id); if (ta) ta.focus(); }
        return;
      }
      if (e.target.id === "empty-reset") {
        S.filters = { ...DEFAULT_FILTERS };
        $("#q").value = "";
        saveFilters();
        renderJobs();
      }
    });

    const onTrackChange = (e) => {
      const sel = e.target.closest("[data-track]");
      if (!sel) return;
      const id = sel.dataset.track;
      setTrack(id, { status: sel.value });
      if (SHEET_STATUSES.has(sel.value)) sheet.add(id);
      const wrap = sel.parentElement;
      wrap.className = "track" + (sel.value ? " st-" + sel.value : "");
      wrap.querySelector(".val").textContent = sel.value ? STATUS_LABEL[sel.value] : "Track";
      if (!$("#view-jobs").hidden) {
        const g = S.groups.find((x) => x.roles.some((r) => r.id === id));
        if (g) {
          rerenderCompany(g.key);
          const again = document.querySelector(`[data-track="${CSS.escape(id)}"]`);
          if (again) again.focus();
        }
      } else {
        renderApps();
      }
    };
    $("#list").addEventListener("change", onTrackChange);
    $("#apps").addEventListener("change", (e) => {
      if (e.target.dataset.applied) { setTrack(e.target.dataset.applied, { applied: e.target.value }); return; }
      onTrackChange(e);
    });

    let noteTimer = null;
    const onNotes = (e) => {
      const el = e.target.closest("[data-notes]");
      if (!el) return;
      clearTimeout(noteTimer);
      noteTimer = setTimeout(() => setTrack(el.dataset.notes, { notes: el.value }), 300);
    };
    $("#list").addEventListener("input", onNotes);
    $("#apps").addEventListener("input", onNotes);

    $("#more").addEventListener("click", () => { S.shown += PAGE; renderJobs(); });

    $("#watchlist").addEventListener("click", (e) => {
      const b = e.target.closest("[data-show-company]");
      if (!b) return;
      S.filters = { ...DEFAULT_FILTERS, q: b.dataset.showCompany, country: "all" };
      $("#q").value = S.filters.q;
      saveFilters();
      location.hash = "#jobs";
    });

    $("#export").addEventListener("click", exportTracker);
    $("#import-file").addEventListener("change", importTracker);

    $("#gist-connect").addEventListener("click", () => gist.connect($("#gist-token").value.trim()));
    $("#gist-sync").addEventListener("click", () => gist.sync(true));
    $("#gist-disconnect").addEventListener("click", () => gist.disconnect());
    $("#sheet-connect").addEventListener("click", () => sheet.connect($("#sheet-url").value.trim(), $("#sheet-secret").value.trim()));
    $("#sheet-backfill").addEventListener("click", () => sheet.backfill());
    $("#sheet-disconnect").addEventListener("click", () => sheet.disconnect());

    window.addEventListener("hashchange", () => setTab(location.hash.slice(1)));
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState !== "visible") return;
      if (gist.cfg && gist.cfg.id) gist.sync(false);
      sheet.flush(false);
    });
    window.addEventListener("storage", (e) => {
      if (e.key === KEYS.tracker) { S.tracker = loadTracker(); render(); }
    });
  }

  function exportTracker() {
    const payload = JSON.stringify({ app: "eu-swe-2027", exported_at: new Date().toISOString(), tracker: S.tracker }, null, 2);
    const blob = new Blob([payload], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `eu-swe-2027-tracker-${todayIso()}.json`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  function importTracker(e) {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed = JSON.parse(String(reader.result));
        const t = parsed.tracker || parsed;
        if (!t || typeof t.items !== "object") throw new Error("not a tracker export");
        const n = Object.values(t.items).filter((x) => x && x.status).length;
        if (!confirm(`Replace your current tracker with ${n} tracked role${n === 1 ? "" : "s"} from ${file.name}?`)) return;
        S.tracker = { v: 1, items: t.items, companies: t.companies && typeof t.companies === "object" ? t.companies : {} };
        saveTracker();
        render();
        toast(`Imported ${n} tracked role${n === 1 ? "" : "s"}.`);
      } catch (err) {
        toast("That file isn't a tracker export.");
      } finally {
        e.target.value = "";
      }
    };
    reader.readAsText(file);
  }

  function mergeItems(a, b) {
    const out = { ...a };
    for (const [id, it] of Object.entries(b || {})) {
      if (!out[id] || (it && (it.u || 0) > (out[id].u || 0))) out[id] = it;
    }
    return out;
  }

  const gist = {
    cfg: store.get(KEYS.gist, null),
    timer: null,
    busy: false,
    lastError: "",

    headers() {
      return { Authorization: `Bearer ${this.cfg.token}`, Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28" };
    },

    async api(path, opts = {}) {
      const res = await fetch(`https://api.github.com${path}`, { ...opts, headers: { ...this.headers(), ...(opts.headers || {}) } });
      if (!res.ok) {
        const msg = res.status === 401 ? "the token was rejected" : res.status === 403 || res.status === 404 ? "the token can't access gists (it needs the gist scope)" : `GitHub returned ${res.status}`;
        throw new Error(msg);
      }
      return res.status === 204 ? null : res.json();
    },

    async connect(token) {
      if (!token) { toast("Paste a GitHub token first."); return; }
      this.cfg = { token, id: null, synced: 0 };
      try {
        let page = 1;
        let found = null;
        while (!found && page <= 5) {
          const list = await this.api(`/gists?per_page=100&page=${page}`);
          found = list.find((g) => g.files && g.files[GIST_FILE]);
          if (list.length < 100) break;
          page++;
        }
        if (found) {
          this.cfg.id = found.id;
        } else {
          const created = await this.api("/gists", {
            method: "POST",
            body: JSON.stringify({ description: "EU SWE 2027 application tracker", public: false, files: { [GIST_FILE]: { content: JSON.stringify(S.tracker) } } }),
          });
          this.cfg.id = created.id;
        }
        store.set(KEYS.gist, this.cfg);
        $("#gist-token").value = "";
        await this.sync(true);
      } catch (err) {
        this.cfg = null;
        store.remove(KEYS.gist);
        toast(`Couldn't connect: ${err.message}.`);
      }
      renderSync();
    },

    disconnect() {
      this.cfg = null;
      store.remove(KEYS.gist);
      renderSync();
      toast("Disconnected. Your Gist is still on GitHub.");
    },

    schedule() {
      if (!this.cfg) return;
      clearTimeout(this.timer);
      this.timer = setTimeout(() => this.sync(false), 3000);
    },

    async sync(loud) {
      if (!this.cfg || !this.cfg.id || this.busy) return;
      this.busy = true;
      try {
        const g = await this.api(`/gists/${this.cfg.id}`);
        const f = g.files && g.files[GIST_FILE];
        let remote = { v: 1, items: {} };
        if (f) {
          let content = f.content;
          if (f.truncated && f.raw_url) content = await (await fetch(f.raw_url)).text();
          try { remote = JSON.parse(content || "{}"); } catch (e) { remote = { v: 1, items: {} }; }
        }
        const merged = { v: 1, items: mergeItems(remote.items || {}, S.tracker.items), companies: mergeItems(remote.companies || {}, S.tracker.companies || {}) };
        const sig = (t) => JSON.stringify([t.items || {}, t.companies || {}]);
        const changedLocal = sig(merged) !== sig(S.tracker);
        const changedRemote = sig(merged) !== sig(remote);
        if (changedLocal) {
          S.tracker = merged;
          store.set(KEYS.tracker, S.tracker);
          render();
        }
        if (changedRemote) {
          await this.api(`/gists/${this.cfg.id}`, { method: "PATCH", body: JSON.stringify({ files: { [GIST_FILE]: { content: JSON.stringify(merged) } } }) });
        }
        this.cfg.synced = Date.now();
        this.lastError = "";
        store.set(KEYS.gist, this.cfg);
        if (loud) toast("Synced with your Gist.");
      } catch (err) {
        this.lastError = err.message;
        if (loud) toast(`Sync failed: ${err.message}.`);
      } finally {
        this.busy = false;
        renderSync();
      }
    },
  };

  const sheet = {
    cfg: store.get(KEYS.sheet, null),
    busy: false,
    lastError: "",

    save() {
      store.set(KEYS.sheet, this.cfg);
    },

    async post(payload) {
      const res = await fetch(this.cfg.url, { method: "POST", body: JSON.stringify({ ...payload, secret: this.cfg.secret }) });
      if (!res.ok) throw new Error(`the script returned ${res.status}`);
      let out;
      try { out = await res.json(); } catch (e) { throw new Error("the script didn't answer with JSON (check it is deployed for \"Anyone\")"); }
      if (!out.ok) throw new Error(out.error || "the script refused the request");
      return out;
    },

    row(id) {
      const t = S.tracker.items[id] || {};
      const r = S.byId.get(id);
      const snap = t.snap || {};
      return {
        id,
        company: r ? r.company : snap.c || "",
        title: r ? r.title : snap.t || "",
        location: cityCountry(r ? r.locations : snap.loc, r ? r.countries : []),
        applied: t.applied || todayIso(),
      };
    },

    add(id) {
      if (!this.cfg) return;
      if (this.cfg.sent.includes(id) || this.cfg.pending.some((p) => p.id === id)) return;
      this.cfg.pending.push(this.row(id));
      this.save();
      this.flush(true);
    },

    async flush(loud) {
      if (!this.cfg || this.busy || !this.cfg.pending.length) return;
      this.busy = true;
      const batch = this.cfg.pending.slice(0, 50);
      try {
        const out = await this.post({ action: "add", rows: batch });
        const ok = new Set(out.ids || []);
        const skipped = new Set(out.skipped || []);
        this.cfg.sent = [...new Set([...this.cfg.sent, ...ok])];
        this.cfg.pending = this.cfg.pending.filter((p) => !ok.has(p.id));
        this.lastError = "";
        this.save();
        if (loud) {
          const added = ok.size - skipped.size;
          if (batch.length === 1) toast(skipped.size ? `${batch[0].company} is already in your sheet.` : `Added ${batch[0].company} to your sheet.`);
          else toast(`Added ${added} application${added === 1 ? "" : "s"} to your sheet` + (skipped.size ? `, ${skipped.size} already there.` : "."));
        }
      } catch (err) {
        this.lastError = err.message;
        if (loud) toast(`Couldn't add to your sheet: ${err.message}. It will retry later.`);
      } finally {
        this.busy = false;
        renderSheet();
      }
      if (this.cfg && this.cfg.pending.length && !this.lastError) this.flush(loud);
    },

    async connect(url, secret) {
      if (!/^https:\/\/script\.google\.com\/macros\/s\/[\w-]+\/exec$/.test(url)) {
        toast("Paste the web app URL from Apps Script (it ends in /exec).");
        return;
      }
      if (!secret) { toast("Enter the secret you set in the script."); return; }
      this.cfg = { url, secret, name: "", sent: [], pending: [] };
      try {
        const out = await this.post({ action: "ping" });
        this.cfg.name = out.sheet || "";
        this.save();
        $("#sheet-secret").value = "";
        toast("Connected to your Google Sheet.");
      } catch (err) {
        this.cfg = null;
        store.remove(KEYS.sheet);
        toast(`Couldn't connect: ${err.message}.`);
      }
      renderSheet();
    },

    backfill() {
      if (!this.cfg) return;
      const ids = Object.entries(S.tracker.items).filter(([, t]) => t && SHEET_STATUSES.has(t.status)).map(([id]) => id);
      const todo = ids.filter((id) => !this.cfg.sent.includes(id) && !this.cfg.pending.some((p) => p.id === id));
      if (!todo.length) { toast("All your applications are already in the sheet."); return; }
      for (const id of todo) this.cfg.pending.push(this.row(id));
      this.save();
      this.flush(true);
    },

    disconnect() {
      this.cfg = null;
      this.lastError = "";
      store.remove(KEYS.sheet);
      renderSheet();
      toast("Disconnected from your sheet. Rows already added stay there.");
    },
  };

  function renderSheet() {
    const on = !!sheet.cfg;
    $("#sheet-off").hidden = on;
    $("#sheet-on").hidden = !on;
    if (!on) return;
    const name = sheet.cfg.name ? `<strong>${esc(sheet.cfg.name)}</strong>` : "your sheet";
    const pending = sheet.cfg.pending.length ? ` ${sheet.cfg.pending.length} waiting to be sent.` : "";
    $("#sheet-status").innerHTML = sheet.lastError
      ? `Connected to ${name}. Last attempt failed: ${esc(sheet.lastError)}.${pending}`
      : `Connected to ${name}. Roles you mark as Applied are added automatically (${sheet.cfg.sent.length} so far).${pending}`;
  }

  function renderSync() {
    const on = !!(gist.cfg && gist.cfg.id);
    $("#sync-off").hidden = on;
    $("#sync-on").hidden = !on;
    if (on) {
      const when = gist.cfg.synced ? new Date(gist.cfg.synced).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "not yet";
      const link = `<a href="https://gist.github.com/${esc(gist.cfg.id)}" target="_blank" rel="noopener">your private Gist</a>`;
      $("#sync-status").innerHTML = gist.lastError
        ? `Connected to ${link}. Last sync failed: ${esc(gist.lastError)}.`
        : `Connected to ${link}. Last synced ${esc(when)}. Changes sync automatically.`;
    }
  }

  async function load() {
    bind();
    setTab(location.hash.slice(1) || "jobs");
    try {
      const res = await fetch("data/roles.json", { cache: "no-cache" });
      if (!res.ok) throw new Error(String(res.status));
      S.data = await res.json();
    } catch (err) {
      $("#stats").textContent = "Couldn't load roles. Try reloading the page.";
      return;
    }
    S.roles = S.data.roles.map((r) => ({
      ...r,
      countries: r.countries || [],
      _co: normCompany(r.company) || fold(r.company),
      _hay: fold(`${r.company} ${r.title} ${r.locations} ${(r.countries || []).map((c) => COUNTRY[c] || c).join(" ")}`),
    }));
    S.byId = new Map(S.roles.map((r) => [r.id, r]));
    populateSelects();
    renderStats();
    render();
    setTab(location.hash.slice(1) || "jobs");
    if (gist.cfg && gist.cfg.id) gist.sync(false);
    sheet.flush(false);
  }

  load();
})();
