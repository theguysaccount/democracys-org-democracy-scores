# Democracys.org open-data companion

**Live:** https://theguysaccount.github.io/democracys-org-democracy-scores/ · **The full site:** https://democracys.org/

Democracys Score v1.0 beta turns five V-Dem democracy indices into one transparent 0–100 score for 179 current countries
and territories, 1900–2025. democracys.org is the full site. This repository builds a static companion that **sits beside
it and replaces nothing**:

- **New, indexed:** embeddable country charts (with V-Dem attribution built in), a public reproducibility report (every
  published value rebuilt monthly from V-Dem's checksum-verified file), and a monthly watch that adopts the next V-Dem
  release automatically when V-Dem publishes it with its citation.
- **Copies, `noindex` with democracys.org as canonical:** 179 country pages, rankings, a three-country comparison and the
  data downloads, so the scores stay available as plain static files.

## Data, method and licence

Five V-Dem Country-Year Core v16 indices (electoral `v2x_polyarchy`, liberal `v2x_liberal`, participatory `v2x_partip`,
deliberative `v2xdl_delib`, egalitarian `v2x_egal`), 20% each. Score = 100 × (½ weighted arithmetic mean + ½ weighted
geometric mean). The derived range applies the same formula to V-Dem's bounds; it is an envelope, not a confidence
interval. Not an official V-Dem score, not endorsed by V-Dem, not externally peer reviewed.

Source: Coppedge et al. (2026), "V-Dem [Country-Year/Country-Date] Dataset v16", Varieties of Democracy (V-Dem) Project,
https://doi.org/10.23696/vdemds26 (full citation on the data page and in `release/vdem.json`). V-Dem data and this adapted
dataset are **CC BY-SA 4.0**. Code: MIT.

## Run

```bash
python3 scripts/reproduce.py        # download V-Dem v16 (16 MB), verify SHA-256, rebuild, compare every value
python3 scripts/release_watch.py    # is there a newer V-Dem release with a stated citation?
python3 site/build.py               # build dist/ (Python 3.9+, standard library only)
python3 -m http.server 8891 --directory dist
```

## Test

```bash
python3 -m unittest discover -s tests -t .   # build script on a V-Dem-shaped fixture, comparison, release parsing, site rules
scripts/e2e.sh                               # headless Chrome: compare three countries, one country page
node scripts/screens.mjs http://127.0.0.1:8891
```

## Layout

| Path | What |
|---|---|
| `scripts/build_democracy_data.py` | The original build script, with the V-Dem release read from `release/vdem.json` (byte-identical v16 output) |
| `public/data/` | The published dataset (the same files democracys.org serves) |
| `release/` | The V-Dem release in use (URL, SHA-256, DOI, citation) and the release history |
| `data/` | Machine-written check results: reproducibility, release watch, live-site status |
| `site/` | The static-site builder and its assets |

Operations, settings and keys: [OPERATIONS.md](OPERATIONS.md).
