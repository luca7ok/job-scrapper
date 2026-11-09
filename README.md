# EU SWE 2027

A personal tracker for **2027 software engineering internships and new-grad roles in Europe**, with continental Europe and mid-size European companies front and centre and July starts highlighted.

- **Site:** https://luca7ok.github.io/job-scrapper/
- **Updates:** every 3 days at 05:00 UTC (07:00 Romanian winter time) via GitHub Actions. New postings, and watchlist companies that just opened, arrive by email.
- **No server, no database, no accounts.** The scraper writes JSON into the repo and GitHub Pages serves it.

## How it works

```
GitHub Actions (every 3 days, 05:00 UTC)
  └─ python -m tracker.update
       ├─ sources        GitHub lists (Simplify, SpeedyApply, EarlyCareers EU),
       │                 179 company job boards (Greenhouse, Lever, Ashby, Workable,
       │                 SmartRecruiters, Workday), Arbeitnow, manual entries
       ├─ filters        entry-level SWE titles, 2027-relevant, located in Europe
       ├─ enrich         start date (July / summer / other), mid-size flag, countries
       ├─ merge + diff   dedupe across sources, first/last seen, new / closed, watchlist hits
       └─ write          site/data/roles.json, data/state.json, data/run_report.md
  └─ commit data → deploy site/ to GitHub Pages
  └─ new roles or watchlist hits → email (Gmail SMTP), or a GitHub issue if email isn't set up
```

A role is marked **closed** only after it has been missing for **2 consecutive healthy runs** of every source that listed it. If a source suddenly returns zero roles, that's treated as an outage and nothing is closed.

## One-time setup

1. **Turn on Pages.** Repo → Settings → Pages → *Build and deployment* → Source: **GitHub Actions**.
2. **Adzuna** is built in but switched off (`settings.aggregators.adzuna: false`). To use it, set it to `true`, add the secrets `ADZUNA_ID` and `ADZUNA_KEY` from https://developer.adzuna.com/, and pass them to the *Run tracker* step in `.github/workflows/update.yml`.
3. **Email alerts.** On days with new postings, the run emails you a list of only the roles first seen that day (watchlist companies that just opened come first, then July starts, then the rest). It sends through Gmail:
   1. Turn on 2-Step Verification for your Google account, then create an app password at https://myaccount.google.com/apppasswords.
   2. Add the secrets `SMTP_USER` (your Gmail address) and `SMTP_PASSWORD` (the 16-character app password).
   3. Optional: `EMAIL_TO` to send to a different address (defaults to `SMTP_USER`).

   If these secrets aren't set, the run opens a GitHub issue labelled `new-roles` instead, which GitHub can email you if you watch the repo's issues.
4. **Phone notifications** (optional). Install the [ntfy](https://ntfy.sh/) app, subscribe to a topic name only you know (e.g. `luca-swe-7f3k2`), and add it as the secret `NTFY_TOPIC`. Every run with new roles then also sends a one-line push.
5. **Run it once by hand.** Actions → *update* → *Run workflow*. The first run fills `data/state.json` and sends nothing (everything would be "new"). From the next run on you'll get an email whenever something new appears, and nothing on days without new postings.

## Editing what it tracks: `config/companies.yaml`

| Section | What it does |
|---|---|
| `settings` | `include_turkey`, `arbeitnow_pages`, and `aggregators: {arbeitnow: true, adzuna: true}` to switch aggregators on or off. |
| `filters` | The title regexes (case-insensitive) that decide what counts as an entry-level SWE role. Edit them without touching code. |
| `ats_companies` | Companies polled through their job board: `{company, ats, slug, midsize}`. `ats` is one of `greenhouse`, `lever`, `ashby`, `workable`, `smartrecruiters`, `workday`. Workday slugs are `tenant\|wdN\|site`, taken from a careers URL like `https://tenant.wdN.myworkdayjobs.com/site`. Add `disabled: true` to stop polling one. |
| `career_site_watchlist` | Companies without a feed. They appear on the Watchlist tab and switch to **Open now** once a matching role shows up from any source. Update `note` and `last_checked` by hand when you check them. |
| `manual_entries` | Roles you found yourself: `{company, title, kind, countries, locations, start, status, midsize, note, url}`. `status: expected` means "not open yet". It shows under *Not open yet*, and a new open role at that company triggers a 🔔 alert. |

Push the change and the next daily run picks it up, or start the workflow by hand.

To check that every slug still responds:

```sh
python scripts/smoke.py --no-fixtures
```

## The application tracker

The status pill next to each role (Saved, Applied, OA, Interview, Offer, Rejected, Withdrawn), the applied date (set automatically when you pick *Applied*) and notes are stored **only in your browser** (`localStorage`, key `tracker.v1`). Nobody else visiting the site can see them.

- **My applications** lists everything you've tracked, including roles that have since closed.
- **Export JSON / Import JSON** for backups or moving between devices by hand. Import replaces the current tracker.
- **Sync across devices:** paste a GitHub token that has only the `gist` scope ([create one](https://github.com/settings/tokens/new?scopes=gist&description=EU%20SWE%202027%20tracker)). The site creates a private Gist named `eu-swe-2027-tracker.json` and keeps it in sync: changes push after a few seconds, and the latest version is pulled whenever the page opens or regains focus. The token stays in that browser's storage and is sent only to `api.github.com`. Disconnecting forgets the token but leaves the Gist.

## Google Sheet

When you mark a role as **Applied** (or jump straight to OA, Interview or Offer), the site adds one row to your Google Sheet. It fills **Company**, **Title**, **Location** (`City, Country`, e.g. `Bucharest, Romania`) and **Application Date** (`MM/dd/yyyy`). **Status**, **Job Posting Link**, **Contact** and **Interview Stage** stay empty for you. Each role is added once. Changing its status later doesn't add it again. Rows you typed in yourself count too: if the sheet already has a row with the same company and a matching title (ignoring case and punctuation, and allowing a shortened title such as "Software Engineer Intern"), the role is skipped and the site says "already in your sheet". When both rows have a location, the city must match as well, so the same title in another city is still added. If a send fails (e.g. you're offline), it is retried the next time the page opens.

Columns are found by their header names in row 1, so their order doesn't matter. An empty sheet gets this header: `Company | Title | Location | Status | Job Posting Link | Contact | Application Date | Interview Stage`.

Set-up (about 5 minutes, free):

1. Open your sheet in Google Sheets → **Extensions → Apps Script**.
2. Delete what's in the editor and paste the contents of [`scripts/google-sheet.gs`](scripts/google-sheet.gs).
3. On the first line, replace `PUT-A-LONG-RANDOM-WORD-HERE` with a long random word of your own (this is your secret). If the sheet you want isn't the first tab, put its name in `SHEET_NAME`. Save.
4. **Deploy → New deployment** → gear icon → **Web app**. Set *Execute as*: **Me**, *Who has access*: **Anyone**. Click **Deploy**.
5. Approve the permissions. Google warns the app "isn't verified" because it's your own script: **Advanced → Go to … (unsafe)** → **Allow**.
6. Copy the **Web app URL** (ends in `/exec`).
7. On the site: **My applications → Google Sheet**, paste the URL and your secret, then **Connect**.
8. Optional: click **Add existing applications** to send roles you marked before connecting.

"Anyone" is required so the site can reach the script without a Google login. The secret is what stops anyone else who finds the URL from writing to your sheet. If you edit the script later, use **Deploy → Manage deployments → Edit → New version** so the URL stays the same.

## Running locally

```sh
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"

.venv/bin/python -m pytest -q                         # unit + pipeline tests
.venv/bin/python -m tracker.update --offline          # full run from tests/fixtures
.venv/bin/python -m tracker.update                    # live run (about 5 minutes)
.venv/bin/python -m tracker.update --only greenhouse  # one source only (repeatable)

cd site && python3 -m http.server 8000                # then open http://localhost:8000
```

Useful flags for `tracker.update`: `--data-dir`, `--site-dir` (write somewhere else), `--today YYYY-MM-DD`, `--no-details` (skip per-job detail requests).

Browser checks (screenshots in both themes, tracker persistence, export/import, mocked Gist sync, Lighthouse) are in `tests/browser/`. They need Node and Chrome:

```sh
cd tests/browser && npm install
npm run serve &          # gzip server on :8766, like GitHub Pages
npm run tracker && npm run gist && npm run shots
```

## Files

| Path | Contents |
|---|---|
| `site/` | The static site (no build step). `site/data/roles.json` is written by the updater. |
| `data/state.json` | Every role ever seen, with first/last seen, status, and per-source health. |
| `data/run_report.md` | Last run: counts per source, errors, outages, new/closed. Also shown in the Actions run summary. |
| `data/history/` | One small JSON snapshot per day (stats, new, closed, hits). |
| `tests/fixtures/` | One real saved response per source, used by the offline run and tests. Refresh with `python scripts/smoke.py`. |

## Sources and etiquette

All sources are public APIs or public GitHub files. Requests share one client with a 20 s timeout, 2 retries, at most 4 at once and about 0.5 s between requests to the same host. The User-Agent identifies the project. LinkedIn, Indeed, Glassdoor and hiring.cafe are never scraped. LinkedIn links that arrive through the EarlyCareers list are only displayed.
