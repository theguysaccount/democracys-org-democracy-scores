# Operations

Live at https://data.democracys.org/, a companion to https://democracys.org/ (which this repo never touches). The first
address, https://theguysaccount.github.io/democracys-org-democracy-scores/, redirects there.

## Automated jobs

| Workflow | When | What it does | How it fails safe |
|---|---|---|---|
| `deploy.yml` | Pushes that change `public/data/`, `release/`, `data/`, `site/` or `scripts/`; dispatched by `monthly.yml` | Tests, static build, headless-Chrome run on the build, Pages deploy (retried once), the same run on the live site, IndexNow for the indexable pages. | Anything failing before the deploy step leaves the last good deploy live. |
| `monthly.yml` | The 8th of each month, 06:43 UTC, or by hand | `release_watch.py` looks for V-Dem v17/v18 and adopts it only with V-Dem's stated citation and passing sanity checks; `reproduce.py` downloads the pinned V-Dem file, verifies its SHA-256, rebuilds and compares every value; `live_check.py` records whether democracys.org answers and which V-Dem version it serves. Commits, redeploys, opens or closes `ops-alert` issues. Keep-alive afterwards. | No check ever edits published data that fails it. A failed download keeps the last good reproducibility result. The run ends red if a check failed. |
| `selftest.yml` | Wednesdays 07:23 UTC, or by hand | `health.py`: pages and files answer, home/reproducibility/embed docs indexable, country pages `noindex` with democracys.org canonical, V-Dem attribution present, monthly checks fresh (dispatches `monthly.yml` if not). Then the live end-to-end run and keep-alive. | Read-only. |
| `ci.yml` | Every push and pull request | Tests on Python 3.9 (Ubuntu 24.04) and 3.12. | — |

**Keep-alive:** `scripts/keepalive.sh` after every scheduled job (re-enables workflows unless disabled by hand; empty
commit after 40 quiet days). **Late schedules:** every job is safe to re-run and the self-test dispatches the monthly checks
when stale.

## What to watch

| Signal | Where | Healthy |
|---|---|---|
| Runs | Actions tab; failure emails to the account owner | Monthly checks and self-test green |
| `ops-alert` issues | Issues tab | None open, except `vdem-newer-than-live` after a V-Dem release (see below) |
| Reproducibility | `/reproducibility/` | "reproduces" (exact or within one rounding step) |

### When an alert opens

- **`vdem-newer-than-live`** (after March 2027): this companion now shows V-Dem v17 and democracys.org still shows v16. Either
  update democracys.org from `public/data/` here, or, while it lags, consider `COUNTRY_PAGES_INDEXABLE=true` (this edition
  then adds newer data). Close the issue when decided.
- **`vdem-new-release`**: V-Dem published a release that could not be adopted yet (citation not stated, download or sanity
  failure). The watch retries monthly; the issue says why.
- **`reproducibility`**: the rebuild no longer matches. Check `release/vdem.json` (URL, SHA-256) and the build script.
- **`live-down`**: democracys.org has not answered for two weeks. If it is gone for good, set `COUNTRY_PAGES_INDEXABLE=true`
  and run `deploy.yml`.

## Scheduled Claude routine (optional)

Not needed for the data, which updates itself. Quarterly, a person or Claude routine can review `ops-alert` and
`correction` issues, and after a V-Dem release read V-Dem's "What's New" notes and add a one-paragraph method note to the
data page (no causal country narratives).

## Keys Jack can turn later

| Key | Why | Exact steps |
|---|---|---|
| **Custom domain** (turned 2026-11-22) | The companion on democracys.org's own domain | In place since the domain rollout on 2026-11-22: Namecheap → democracys.org → Advanced DNS has `CNAME data → theguysaccount.github.io.`, the Pages custom domain is `data.democracys.org` with HTTPS enforced, and the repo variable `SITE_URL` is `https://data.democracys.org`, the one setting every page, sitemap and check reads. The apex and www records stay as they are. **To move to another host:** add its CNAME, then `~/.local/bin/gh api -X PUT repos/theguysaccount/democracys-org-democracy-scores/pages -f cname=<host>`, `~/.local/bin/gh variable set SITE_URL -R theguysaccount/democracys-org-democracy-scores -b https://<host>`, `~/.local/bin/gh workflow run deploy.yml -R theguysaccount/democracys-org-democracy-scores`, and once the certificate is issued `~/.local/bin/gh api -X PUT repos/theguysaccount/democracys-org-democracy-scores/pages -F https_enforced=true`; then delete the old CNAME. **To go back to github.io:** `~/.local/bin/gh api -X PUT repos/theguysaccount/democracys-org-democracy-scores/pages --input - <<< '{"cname":null}'`, `~/.local/bin/gh variable delete SITE_URL -R theguysaccount/democracys-org-democracy-scores`, `~/.local/bin/gh workflow run deploy.yml -R theguysaccount/democracys-org-democracy-scores`, then delete `CNAME data` at Namecheap straight away: a CNAME left pointing at GitHub Pages with no site claiming it can be taken over. |
| **Money: grant or classroom sponsor** | First revenue without breaking Pages' non-commercial terms | `gh variable set SUPPORT_URL -b <url>` (and `SUPPORT_LABEL`), run `deploy.yml`. Never paid ranking placement. |
| **Analytics** | Count embeds and downloads | GoatCounter site, `gh variable set GOATCOUNTER_URL -b https://<code>.goatcounter.com/count`, run `deploy.yml`. |
| **Named editor and corrections** | The original's priority #1 for trust | Name an editor and a corrections address on democracys.org; correction issues here already work. |
| **Index the country pages** | Only when this edition carries newer data or the live site is retired | `gh variable set COUNTRY_PAGES_INDEXABLE -b true`, run `deploy.yml`. |
