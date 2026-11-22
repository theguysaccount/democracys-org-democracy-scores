"""Build the static Democracys.org companion into dist/.

    python3 site/build.py [--out dist]

Settings (environment, all optional):
  SITE_URL                 public base URL, no trailing slash (default: the GitHub Pages URL)
  SITE_REPO                owner/name of the repo
  LIVE_URL                 the live site (default https://democracys.org); duplicated pages point their canonical there
  COUNTRY_PAGES_INDEXABLE  "true" makes the country, ranking, compare and data pages indexable and self-canonical
                           (only when this edition shows data the live site does not, or the live site is retired)
  GOATCOUNTER_URL, SUPPORT_URL, SUPPORT_LABEL, BUILD_DATE

Pages that add something the live site lacks (the home page, reproducibility, embeds) are always indexable.
"""
import argparse
import csv
import datetime
import html
import io
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
FIELDS = ("electoral", "liberal", "participatory", "deliberative", "egalitarian")
LABEL = {"electoral": "Electoral", "liberal": "Liberal", "participatory": "Participatory",
         "deliberative": "Deliberative", "egalitarian": "Egalitarian"}
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")


def e(v):
    return html.escape("" if v is None else str(v), quote=True)


def long_date(iso):
    if not iso:
        return ""
    y, m, d = iso[:10].split("-")
    return "%d %s %s" % (int(d), MONTHS[int(m) - 1], y)


def signed(v):
    return "n/a" if v is None else ("%+.1f" % v).replace("+0.0", "0.0").replace("-0.0", "0.0")


class Cfg(object):
    def __init__(self, env):
        self.url = (env.get("SITE_URL") or "https://theguysaccount.github.io/democracys-org-democracy-scores").rstrip("/")
        self.repo = env.get("SITE_REPO") or "theguysaccount/democracys-org-democracy-scores"
        self.repo_url = "https://github.com/" + self.repo
        self.live = (env.get("LIVE_URL") or "https://democracys.org").rstrip("/")
        self.country_indexable = (env.get("COUNTRY_PAGES_INDEXABLE") or "false").lower() == "true"
        self.goatcounter = (env.get("GOATCOUNTER_URL") or "").strip()
        self.support_url = (env.get("SUPPORT_URL") or "").strip()
        self.support_label = (env.get("SUPPORT_LABEL") or "Support Democracys.org").strip()
        self.built = env.get("BUILD_DATE") or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------- charts (static SVG)

def chart(history, width=720, height=260, label=""):
    """Score line with the derived lower-upper envelope, 1900 to the latest year, 0-100."""
    pad_l, pad_r, pad_t, pad_b = 34, 10, 10, 26
    years = [p["year"] for p in history]
    y0, y1 = 1900, max(years)
    sx = lambda y: pad_l + (y - y0) / float(max(1, y1 - y0)) * (width - pad_l - pad_r)  # noqa: E731
    sy = lambda v: pad_t + (1 - v / 100.0) * (height - pad_t - pad_b)  # noqa: E731
    segments, seg = [], []
    for p in history:   # gaps (years without data) break the line
        if seg and p["year"] != seg[-1]["year"] + 1:
            segments.append(seg)
            seg = []
        seg.append(p)
    if seg:
        segments.append(seg)
    parts = []
    for v in (0, 25, 50, 75, 100):
        parts.append('<line class="grid" x1="%d" x2="%d" y1="%.1f" y2="%.1f"/><text class="ax" x="%d" y="%.1f">%d</text>'
                     % (pad_l, width - pad_r, sy(v), sy(v), pad_l - 6, sy(v) + 4, v))
    for y in range(1900, y1 + 1, 25):
        parts.append('<text class="ax" x="%.1f" y="%d" text-anchor="middle">%d</text>' % (sx(y), height - 6, y))
    for s in segments:
        band = " ".join("%.1f,%.1f" % (sx(p["year"]), sy(p["upper"])) for p in s) + " " + " ".join(
            "%.1f,%.1f" % (sx(p["year"]), sy(p["lower"])) for p in reversed(s))
        parts.append('<polygon class="band" points="%s"/>' % band)
        parts.append('<polyline class="line" points="%s"/>' % " ".join("%.1f,%.1f" % (sx(p["year"]), sy(p["score"])) for p in s))
    last = history[-1]
    parts.append('<circle class="dot" cx="%.1f" cy="%.1f" r="4"/>' % (sx(last["year"]), sy(last["score"])))
    return ('<svg class="chart" viewBox="0 0 %d %d" role="img" aria-label="%s">%s</svg>'
            % (width, height, e(label or "Democracys Score by year, with derived uncertainty envelope"), "".join(parts)))


# ---------------------------------------------------------------- page shell

def attribution(release, root):
    return ('Data: Democracys Score v1.0 beta, an experimental transformation of %s (%s, <a href="%s">%s</a>), '
            'licensed <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>. Not an official V-Dem '
            'score and not endorsed by V-Dem. <a href="%sdata/#cite">Full citation</a>.'
            % (e(release["label"]), e(release["shortAttribution"].split(",")[0]), e(release["doi"]),
               e(release["doi"].replace("https://", "")), root))


def page(cfg, release, rel, title, desc, body, depth, index=True, canonical=None, scripts=(), og="og.png"):
    root = "../" * depth
    robots = "" if index else '<meta name="robots" content="noindex">\n'
    gc = ('<script data-goatcounter="%s" async src="https://gc.zgo.at/count.js"></script>\n' % e(cfg.goatcounter)) if cfg.goatcounter else ""
    canon = canonical or (cfg.url + "/" + rel)
    support = ('<p><a class="support" href="%s" rel="noopener">%s</a></p>' % (e(cfg.support_url), e(cfg.support_label))) if cfg.support_url else ""
    doc = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
{robots}<link rel="canonical" href="{canon}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Democracys.org open data">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{self_url}">
<meta property="og:image" content="{og}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{root}assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{root}assets/style.css">
{gc}</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="top"><a class="brand" href="{root}">Democracys<span>.org</span> <small>open data</small></a>
<nav aria-label="Site"><a href="{root}rankings/">Rankings</a><a href="{root}compare/">Compare</a><a href="{root}embed/">Embed</a><a href="{root}reproducibility/">Reproducibility</a><a href="{root}data/">Data</a><a href="{live}/">Full site &rarr;</a></nav></header>
<main id="main">
{body}
</main>
<footer class="foot">
<p>{attribution}</p>
<p>This is the static, open-data edition of <a href="{live}/">Democracys.org</a>: the same scores, plus embeds, a public reproducibility check and
a monthly watch for new V-Dem releases. Scores describe political systems in a given year, not the worth of a country, culture or people.
<a href="{repo_url}">Source on GitHub</a> &middot; <a href="{repo_url}/issues/new?template=correction.yml">Report an error</a> &middot; built {built}</p>
{support}
</footer>
{scripts}</body>
</html>
""".format(title=e(title), desc=e(desc), robots=robots, canon=e(canon), self_url=e(cfg.url + "/" + rel),
           og=e(cfg.url + "/" + og), root=root, gc=gc, body=body, live=e(cfg.live),
           attribution=attribution(release, root), repo_url=e(cfg.repo_url), built=e(long_date(cfg.built)),
           support=support, scripts="".join('<script type="module" src="%sassets/%s"></script>\n' % (root, s) for s in scripts))
    return doc


# ---------------------------------------------------------------- pages

def score_cell(p):
    return '<b>%.1f</b> <span class="muted">(%.1f&ndash;%.1f)</span>' % (p["score"], p["lower"], p["upper"])


def country_page(cfg, release, data, c):
    latest = c["latest"]
    year = latest["year"]
    rows = "".join('<tr><td>%d</td><td class="num">%s</td>%s</tr>' % (
        p["year"], score_cell(p), "".join('<td class="num hidesm">%.1f</td>' % p[f] for f in FIELDS)) for p in reversed(c["history"][-10:]))
    comps = "".join('<tr><th scope="row">%s</th><td class="num">%.1f</td><td><div class="meter"><i style="width:%.1f%%"></i></div></td></tr>'
                    % (LABEL[f], latest[f], latest[f], ) for f in FIELDS)
    changes = " &middot; ".join("%s %s <b>%s</b>" % (w, "year" if w == "1" else "years", signed(c["changes"].get(w))) for w in ("1", "5", "10", "25"))
    live = "%s/countries/%s" % (cfg.live, c["slug"])
    embed = '<iframe src="%s/embed/%s/" title="Democracys Score: %s" width="100%%" height="380" style="border:0;max-width:720px" loading="lazy"></iframe>' % (
        cfg.url, c["slug"], c["name"])
    body = """
<p class="note-bar">Static copy. The full profile, with the change explorer and a printable brief, is at <a href="{live}">{live_short}</a>.</p>
<article class="country" data-country="{slug}">
<h1>{name}</h1>
<p class="lede">Democracys Score <b>{score:.1f}</b> in {year} (derived range {lower:.1f}&ndash;{upper:.1f}), rank {rank} of {total}.
Weakest of the five tests: <b>{weakest}</b>.</p>
<p class="muted">Change in score to {year}: {changes}.</p>
{chart}
<h2>The five tests in {year}</h2>
<table class="comps">{comps}</table>
<p class="muted">Each test is a V-Dem index rescaled to 0&ndash;100: electoral (<code>v2x_polyarchy</code>), liberal (<code>v2x_liberal</code>),
participatory (<code>v2x_partip</code>), deliberative (<code>v2xdl_delib</code>), egalitarian (<code>v2x_egal</code>).</p>
<h2>Last ten years</h2>
<div class="tablewrap"><table><thead><tr><th>Year</th><th class="num">Score (range)</th>{heads}</tr></thead><tbody>{rows}</tbody></table></div>
<h2>Download and embed</h2>
<p><a href="../../data/countries/{slug}.csv" download>{name}, every year (CSV)</a> &middot; <a href="../../data/countries/{slug}.json">JSON</a></p>
<p>Embed this chart (it credits V-Dem and links back):</p>
<pre class="code"><code>{embed}</code></pre>
</article>
""".format(live=e(live), live_short=e(live.replace("https://", "")), slug=e(c["slug"]), name=e(c["name"]),
           score=latest["score"], year=year, lower=latest["lower"], upper=latest["upper"], rank=c["rank"],
           total=c["totalRanked"], weakest=e(LABEL[c["weakest"]].lower()), changes=changes,
           chart=chart(c["history"], label="%s: Democracys Score 1900 to %d" % (c["name"], year)), comps=comps,
           heads="".join('<th class="num hidesm">%s</th>' % LABEL[f] for f in FIELDS), rows=rows, embed=e(embed))
    return page(cfg, release, "countries/%s/" % c["slug"],
                "%s democracy score %d: %.1f (rank %d of %d)" % (c["name"], year, latest["score"], c["rank"], c["totalRanked"]),
                "%s scores %.1f out of 100 on the Democracys Score for %d, based on V-Dem data from 1900 to %d. Five tests, uncertainty range and downloadable data."
                % (c["name"], latest["score"], year, year), body, 2, index=cfg.country_indexable,
                canonical=None if cfg.country_indexable else live)


def embed_page(cfg, release, c):
    latest = c["latest"]
    live = "%s/countries/%s" % (cfg.live, c["slug"])
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name}: Democracys Score (embed)</title><meta name="robots" content="noindex"><link rel="canonical" href="{live}">
<link rel="stylesheet" href="../../assets/style.css"></head>
<body class="embed"><div class="ecard">
<p class="kicker">Democracys Score, 1900&ndash;{year}</p>
<h1 class="etitle"><a href="{live}" target="_blank" rel="noopener">{name}</a> <span>{score:.1f}</span></h1>
{chart}
<p class="eattr">Democracys.org transformation of {label} (<a href="{doi}" target="_blank" rel="noopener">V-Dem</a>), CC BY-SA 4.0. Not an official V-Dem score.
<a href="{live}" target="_blank" rel="noopener">Full profile &rarr;</a></p>
</div></body></html>
""".format(name=e(c["name"]), live=e(live), year=latest["year"], score=latest["score"],
           chart=chart(c["history"], 640, 220, "%s: Democracys Score by year" % c["name"]), label=e(release["label"]),
           doi=e(release["doi"]))


def rankings_page(cfg, release, data):
    countries = sorted(data["countries"], key=lambda c: c["rank"])
    year = data["meta"]["observationYears"][1]
    rows = "".join('<tr><td class="num">%d</td><td><a href="../countries/%s/">%s</a></td><td class="num">%s</td><td class="num hidesm">%s</td></tr>'
                   % (c["rank"], e(c["slug"]), e(c["name"]), score_cell(c["latest"]), signed(c["changes"].get("10"))) for c in countries)
    body = """
<p class="note-bar">Static copy. The full rankings are at <a href="{live}/rankings">{live_short}/rankings</a>.</p>
<h1>Democracy rankings, {year}</h1>
<p class="lede">All {n} current countries and territories by Democracys Score v1.0 beta, {year}. Ranks are navigation aids: small gaps can sit inside
the derived range.</p>
<div class="tablewrap"><table><thead><tr><th class="num">Rank</th><th>Country</th><th class="num">Score (range)</th><th class="num hidesm">10-year change</th></tr></thead>
<tbody>{rows}</tbody></table></div>""".format(live=e(cfg.live), live_short=e(cfg.live.replace("https://", "")), year=year,
                                              n=len(countries), rows=rows)
    return page(cfg, release, "rankings/", "Democracy rankings %d: %d countries by Democracys Score" % (year, len(countries)),
                "All %d countries and territories ranked by Democracys Score v1.0 beta for %d, from V-Dem data." % (len(countries), year),
                body, 1, index=cfg.country_indexable, canonical=None if cfg.country_indexable else cfg.live + "/rankings")


def compare_page(cfg, release, data):
    options = "".join('<option value="%s">%s</option>' % (e(c["slug"]), e(c["name"])) for c in sorted(data["countries"], key=lambda c: c["name"]))
    body = """
<p class="note-bar">Static copy. The full comparison tool is at <a href="{live}/compare">{live_short}/compare</a>.</p>
<h1>Compare countries</h1>
<p class="lede">Pick up to three. The chart draws each country's Democracys Score from 1900; the address keeps your choice so you can share it.</p>
<form id="compare" class="compare" onsubmit="return false">
{selects}
</form>
<div id="compare-chart" aria-live="polite"></div>
<noscript><p>The comparison needs JavaScript. Every country page works without it.</p></noscript>""".format(
        live=e(cfg.live), live_short=e(cfg.live.replace("https://", "")),
        selects="".join('<label>Country %d <select name="c%d"><option value="">(none)</option>%s</select></label>' % (i, i, options) for i in (1, 2, 3)))
    return page(cfg, release, "compare/", "Compare democracy scores between countries, 1900 to %d" % data["meta"]["observationYears"][1],
                "Compare the Democracys Score of up to three countries since 1900.", body, 1, index=cfg.country_indexable,
                canonical=None if cfg.country_indexable else cfg.live + "/compare", scripts=("compare.js",))


def data_page(cfg, release, data, history):
    meta = data["meta"]
    rel_rows = "".join('<tr><td>%s</td><td>%s</td><td class="num">%s</td><td><code>%s&hellip;</code></td><td>%s</td></tr>'
                       % (e(h["date"]), e(h["version"]), "{:,}".format(h["observations"]), e(h["sha256"][:16]), e(h["note"])) for h in history)
    body = """
<h1>Data</h1>
<p class="lede">The complete Democracys Score dataset, {countries} countries and territories, {obs:,} country-years, {y0}&ndash;{y1}.</p>
<ul class="downloads">
<li><a href="democracys-score-v1.csv" download>democracys-score-v1.csv</a>: one row per country-year: score, derived range and the five tests</li>
<li><a href="democracys-score-v1.json">democracys-score-v1.json</a>: the same, grouped by country, with rank and recent changes</li>
<li><a href="README.txt">README.txt</a>: source, method and licence</li>
<li>One file per country: <code>data/countries/&lt;slug&gt;.csv</code> and <code>.json</code> (linked from every country page)</li>
<li><a href="reproducibility.json">reproducibility.json</a> and <a href="release-watch.json">release-watch.json</a>: the latest automated checks</li>
</ul>
<h2 id="cite">Source, licence and citation</h2>
<p>The scores transform five indices from {label} ({published}), downloaded from <a href="{url}">{url}</a> and verified by SHA-256
<code>{sha}</code>. V-Dem publishes its data under <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>; this adapted dataset uses
the same licence, as the share-alike terms require. Cite the source as V-Dem asks:</p>
<blockquote class="cite">{citation}</blockquote>
<p>and this transformation as: Democracys.org (2026), Democracys Score v1.0 beta, method version {method}, {self_url}.</p>
<p class="muted">Democracys Score is an experimental transformation, not an official V-Dem score, and is not endorsed by V-Dem. V-Dem advises against comparing
index values across dataset versions, so every release replaces the whole series.</p>
<h2>Release history</h2>
<div class="tablewrap"><table><thead><tr><th>Date</th><th>Source</th><th class="num">Rows</th><th>SHA-256</th><th>Note</th></tr></thead><tbody>{rel_rows}</tbody></table></div>
""".format(countries=meta["countryCount"], obs=meta["observationCount"], y0=meta["observationYears"][0], y1=meta["observationYears"][1],
           label=e(release["label"]), published=e(release["publishedLong"]), url=e(release["sourceUrl"]), sha=e(release["sha256"]),
           citation=e(release["citation"]), method=e(meta["methodVersion"]), self_url=e(cfg.url + "/"), rel_rows=rel_rows)
    return page(cfg, release, "data/", "Democracy score data download: CSV and JSON, %d countries, %d to %d" % (
        meta["countryCount"], meta["observationYears"][0], meta["observationYears"][1]),
        "Download the Democracys Score dataset (CC BY-SA 4.0) built from V-Dem: every country-year, the five tests and the derived range.",
        body, 1, index=cfg.country_indexable, canonical=None if cfg.country_indexable else cfg.live + "/data")


def reproducibility_page(cfg, release, repro, watch):
    if not repro:
        body = "<h1>Reproducibility</h1><p class=\"lede\">The first automated check has not run yet.</p>"
    else:
        verdict = {"exact": "Every published value reproduces exactly.",
                   "rounding": "Every published value reproduces, %d of %s exactly; %d differ by one rounding step (0.1)." % (
                       repro.get("exact", 0), "{:,}".format(repro.get("values", 0)), repro.get("differenceCount", 0)),
                   "failed": "The rebuild did not match. An issue has been opened; the published data was not changed.",
                   "unverified": "V-Dem's file could not be downloaded on the last attempt."}[repro["verdict"]]
        diffs = "".join('<tr><td>%s</td><td>%s</td><td>%s</td><td class="num">%s</td><td class="num">%s</td></tr>' % (
            e(d["country"]), d["year"], e(d["field"]), d["published"], d["rebuilt"]) for d in repro.get("differences", [])[:50])
        body = """
<h1>Can you get the same numbers?</h1>
<p class="lede">Yes. Every month a scheduled job downloads V-Dem's official file, checks its SHA-256, runs the published build script and compares
every one of the {values} published values with the rebuild.</p>
<div class="verdict verdict-{v}" data-verdict="{v}"><b>{verdict}</b><br><span class="muted">Last check {checked}: {label}, checksum {checksum},
{countries} countries, {rows:,} country-years.</span></div>
<h2>How to reproduce it yourself</h2>
<ol>
<li>Download <a href="{url}">{url_short}</a>.</li>
<li>Check its SHA-256 is <code>{sha}</code>.</li>
<li>Run <code>python3 scripts/build_democracy_data.py V-Dem-CY-Core-{ver}.csv .</code> from <a href="{repo}">the repository</a> (Python 3, no packages).</li>
<li>Compare with <a href="../data/democracys-score-v1.csv">the published CSV</a>.</li>
</ol>
{diff_block}
<h2>New V-Dem releases</h2>
<p>V-Dem publishes a new version each March. The same job looks for it monthly; when it appears and V-Dem states its citation, the whole series is
rebuilt from it (V-Dem advises against comparing values across versions). Last look: {wchecked}, {wnote}.</p>""".format(
            values="{:,}".format(repro.get("values", 0)), v=e(repro["verdict"]), verdict=e(verdict),
            checked=e(long_date(repro.get("checked"))), label=e(release["label"]), checksum=e(repro.get("checksum")),
            countries=repro.get("countries", 0), rows=repro.get("rows", 0), url=e(release["sourceUrl"]),
            url_short=e(release["sourceUrl"].replace("https://", "")), sha=e(release["sha256"]), ver=e(release["version"]),
            repo=e(cfg.repo_url),
            diff_block=("<h2>The values that differ by one rounding step</h2><p class=\"muted\">These sit exactly on a rounding boundary, where the last "
                        "decimal depends on floating-point details of the machine.</p><div class=\"tablewrap\"><table><thead><tr><th>Country</th><th>Year</th>"
                        "<th>Field</th><th class=\"num\">Published</th><th class=\"num\">Rebuilt</th></tr></thead><tbody>%s</tbody></table></div>" % diffs) if diffs else "",
            wchecked=e(long_date((watch or {}).get("checked"))), wnote=e((watch or {}).get("note", "not run yet")))
    return page(cfg, release, "reproducibility/", "Reproducible democracy scores: rebuilt monthly from V-Dem's official data",
                "Every Democracys Score value is rebuilt monthly from V-Dem's checksum-verified file and compared with the published data.",
                body, 1, index=True)


def embed_docs(cfg, release, data):
    example = sorted(data["countries"], key=lambda c: c["name"])[0]
    code = '<iframe src="%s/embed/%s/" title="Democracys Score: %s" width="100%%" height="380" style="border:0;max-width:720px" loading="lazy"></iframe>' % (
        cfg.url, example["slug"], example["name"])
    opts = "".join('<li><a href="%s/">%s</a></li>' % (e(c["slug"]), e(c["name"])) for c in sorted(data["countries"], key=lambda c: c["name"]))
    body = """
<h1>Embed a democracy score chart</h1>
<p class="lede">A chart of any country's Democracys Score since 1900, with its derived range, ready to paste into a lesson, article or report.
It carries the V-Dem attribution and the CC BY-SA 4.0 licence, as the source's terms require, and links to the full profile.</p>
<pre class="code"><code>{code}</code></pre>
<p>Replace <code>{slug}</code> with any country below. The chart is static: no cookies, no tracking, no script.</p>
<iframe src="{slug}/" title="Example embed" width="100%" height="380" style="border:0;max-width:720px" loading="lazy"></iframe>
<h2>All {n} countries</h2><ul class="cols">{opts}</ul>""".format(code=e(code), slug=e(example["slug"]), n=len(data["countries"]), opts=opts)
    return page(cfg, release, "embed/", "Embed a democracy score chart for any country (free, CC BY-SA)",
                "Free embeddable charts of the Democracys Score for %d countries since 1900, with V-Dem attribution built in." % len(data["countries"]),
                body, 1, index=True)


def home_page(cfg, release, data, repro, watch):
    meta = data["meta"]
    year = meta["observationYears"][1]
    ranked = sorted(data["countries"], key=lambda c: c["rank"])
    row = lambda c: '<li><a href="countries/%s/">%s</a> <b>%.1f</b></li>' % (e(c["slug"]), e(c["name"]), c["latest"]["score"])  # noqa: E731
    rv = (repro or {}).get("verdict")
    repro_line = {"exact": "every published value reproduces exactly", "rounding": "every published value reproduces (a few to within one rounding step)",
                  "failed": "the last rebuild did not match; under review", "unverified": "the last download failed; the previous check stands"}.get(rv, "first check pending")
    body = """
<section class="intro">
<h1>Democracy scores for {n} countries, 1900&ndash;{year}, as open data</h1>
<p class="lede">Democracys Score turns five V-Dem democracy indices into one transparent 0&ndash;100 score for every current country and territory.
This edition adds what a classroom, newsroom or researcher needs to reuse it: <a href="embed/">embeddable charts</a>, per-country downloads, and a
<a href="reproducibility/">public monthly rebuild</a> from V-Dem's checksum-verified file.</p>
<p>Explore everything, including the change explorer, teaching toolkit and printable briefs, at <a href="{live}/">democracys.org</a>.</p>
<p class="muted">Reproducibility: {repro_line}{rchecked}. V-Dem release watch: {wnote}.</p>
</section>
<div class="two">
<section><h2>Highest scores, {year}</h2><ol class="mini">{top}</ol></section>
<section><h2>Lowest scores, {year}</h2><ol class="mini" start="{start}">{bottom}</ol></section>
</div>
<p><a class="button" href="rankings/">All {n} countries</a> <a class="button ghost" href="compare/">Compare countries</a> <a class="button ghost" href="data/">Download the data</a></p>
<section><h2>What the score is, and is not</h2>
<p>The score is 100 times an equal blend of the weighted arithmetic and geometric means of V-Dem's electoral, liberal, participatory, deliberative
and egalitarian indices (20% each). The range shown beside each score applies the same formula to V-Dem's bounds; it is an envelope, not a
confidence interval. Rankings are navigation aids: small gaps can sit inside that range. The method is a beta that has not been externally
peer reviewed.</p></section>""".format(
        n=meta["countryCount"], year=year, live=e(cfg.live), repro_line=e(repro_line),
        rchecked=(", checked %s" % e(long_date(repro.get("checked")))) if repro else "",
        wnote=e((watch or {}).get("note", "first check pending")), top="".join(row(c) for c in ranked[:10]),
        bottom="".join(row(c) for c in ranked[-10:]), start=len(ranked) - 9)
    return page(cfg, release, "", "Democracy scores by country, 1900 to %d: open data, charts and embeds" % year,
                "Free democracy scores for %d countries and territories from 1900 to %d, built from V-Dem: download the data, embed a chart, check the rebuild."
                % (meta["countryCount"], year), body, 0, index=True)


# ---------------------------------------------------------------- files

def country_files(dist, data):
    os.makedirs(os.path.join(dist, "data", "countries"), exist_ok=True)
    for c in data["countries"]:
        with open(os.path.join(dist, "data", "countries", c["slug"] + ".json"), "w", encoding="utf-8") as fh:
            json.dump({"meta": data["meta"], "country": c}, fh, ensure_ascii=False, separators=(",", ":"))
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["country", "country_code", "year", "democracys_score", "derived_lower", "derived_upper"] + list(FIELDS))
        for p in c["history"]:
            w.writerow([c["name"], c["code"], p["year"], p["score"], p["lower"], p["upper"]] + [p[f] for f in FIELDS])
        with open(os.path.join(dist, "data", "countries", c["slug"] + ".csv"), "w", encoding="utf-8") as fh:
            fh.write(buf.getvalue())


def build(out=None, env=None):
    env = os.environ if env is None else env
    cfg = Cfg(env)
    dist = out or os.path.join(ROOT, "dist")
    load = lambda *p, **kw: json.load(open(os.path.join(ROOT, *p), encoding="utf-8")) if os.path.exists(os.path.join(ROOT, *p)) else kw.get("default")  # noqa: E731
    data = load("public", "data", "democracys-score-v1.json")
    release = load("release", "vdem.json")
    history = load("release", "history.json", default=[])
    repro = load("data", "reproducibility.json")
    watch = load("data", "release-watch.json")
    assert data["meta"]["countryCount"] == len(data["countries"]) > 0, "dataset is empty or inconsistent"
    if os.path.exists(dist):
        shutil.rmtree(dist)
    shutil.copytree(os.path.join(SITE, "assets"), os.path.join(dist, "assets"))
    shutil.copy(os.path.join(SITE, "og.png"), os.path.join(dist, "og.png"))
    pages = []

    def write(rel, text, indexable):
        full = os.path.join(dist, rel, "index.html") if not rel.endswith(".html") else os.path.join(dist, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(text)
        if indexable:
            pages.append(rel)

    write("", home_page(cfg, release, data, repro, watch), True)
    write("reproducibility/", reproducibility_page(cfg, release, repro, watch), True)
    write("embed/", embed_docs(cfg, release, data), True)
    write("rankings/", rankings_page(cfg, release, data), cfg.country_indexable)
    write("compare/", compare_page(cfg, release, data), cfg.country_indexable)
    write("data/", data_page(cfg, release, data, history), cfg.country_indexable)
    for c in data["countries"]:
        write("countries/%s/" % c["slug"], country_page(cfg, release, data, c), cfg.country_indexable)
        write("embed/%s/" % c["slug"], embed_page(cfg, release, c), False)
    write("404.html", page(cfg, release, "404.html", "Page not found", "Page not found.",
                           '<h1>Page not found</h1><p class="lede"><a href="%s/">Back to the scores</a></p>' % e(cfg.url), 0, index=False), False)
    for name in ("democracys-score-v1.json", "democracys-score-v1.csv", "README.txt"):
        shutil.copy(os.path.join(ROOT, "public", "data", name), os.path.join(dist, "data", name))
    for name in ("reproducibility.json", "release-watch.json"):
        if os.path.exists(os.path.join(ROOT, "data", name)):
            shutil.copy(os.path.join(ROOT, "data", name), os.path.join(dist, "data", name))
    country_files(dist, data)
    with open(os.path.join(dist, "data", "countries.json"), "w", encoding="utf-8") as fh:
        json.dump([{"slug": c["slug"], "name": c["name"]} for c in sorted(data["countries"], key=lambda c: c["name"])], fh, ensure_ascii=False)
    key = open(os.path.join(SITE, "indexnow-key.txt")).read().strip()
    with open(os.path.join(dist, key + ".txt"), "w") as fh:
        fh.write(key + "\n")
    with open(os.path.join(dist, "robots.txt"), "w") as fh:
        fh.write("User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % cfg.url)
    with open(os.path.join(dist, "sitemap.xml"), "w") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</urlset>\n' % "\n".join(
            "<url><loc>%s</loc><lastmod>%s</lastmod></url>" % (e(cfg.url + "/" + p), cfg.built) for p in pages))
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    with open(os.path.join(ROOT, "build", "urls.txt"), "w") as fh:
        fh.write("\n".join(cfg.url + "/" + p for p in pages) + "\n")
    return cfg, data, pages


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    a = ap.parse_args()
    cfg, data, pages = build(a.out)
    print("built %d countries, %d indexable pages, for %s" % (len(data["countries"]), len(pages), cfg.url))
