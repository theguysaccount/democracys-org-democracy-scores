"""Weekly self-test of the live companion: pages and files answer, indexing matches the configuration per page type,
attribution is present, and the monthly checks are fresh (dispatches monthly.yml when they are not).

    python3 scripts/health.py [base_url]
"""
import datetime
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

UA = "democracys-org-democracy-scores-selftest/1.0 (+https://github.com/theguysaccount/democracys-org-democracy-scores)"
LIVE = (os.environ.get("LIVE_URL") or "https://democracys.org").rstrip("/")


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return exc.code, ""
        except Exception as exc:
            last = str(exc)
        time.sleep(3 * (i + 1))
    return 0, last


def main(base):
    base = base.rstrip("/")
    indexable = (os.environ.get("COUNTRY_PAGES_INDEXABLE") or "false").lower() == "true"
    lines, failed, stale = ["## Live companion", ""], False, False

    def ok(good, text):
        nonlocal failed
        lines.append("- %s %s" % ("ok  " if good else "FAIL", text))
        failed |= not good

    b = "?selftest=%d" % int(time.time())
    st, raw = get(base + "/data/democracys-score-v1.json" + b)
    try:
        data = json.loads(raw)
        ok(len(data["countries"]) == data["meta"]["countryCount"] > 0, "dataset: %d countries, %s" % (len(data["countries"]), data["meta"]["source"]))
    except Exception as exc:
        data = None
        ok(False, "dataset: %s" % exc)
    slug = data["countries"][0]["slug"] if data else "united-states"
    pages = {p: get(base + p + b) for p in ("/", "/reproducibility/", "/embed/", "/rankings/", "/compare/", "/data/",
                                            "/countries/%s/" % slug, "/embed/%s/" % slug, "/data/countries/%s.csv" % slug,
                                            "/robots.txt", "/sitemap.xml", "/assets/compare.js")}
    for p, (st, _) in pages.items():
        ok(st == 200, "%s (%s)" % (p, st))
    noindex = lambda h: 'name="robots" content="noindex"' in h  # noqa: E731
    ok(not any(noindex(pages[p][1]) for p in ("/", "/reproducibility/", "/embed/")), "home, reproducibility and embed docs are indexable")
    country = pages["/countries/%s/" % slug][1]
    if indexable:
        ok(not noindex(country), "country pages indexable (COUNTRY_PAGES_INDEXABLE=true)")
    else:
        ok(noindex(country) and ('<link rel="canonical" href="%s/countries/%s">' % (LIVE, slug)) in country,
           "country pages are noindex with democracys.org as canonical")
    ok("CC BY-SA 4.0" in country and "not endorsed by V-Dem" in country, "V-Dem attribution and licence on country pages")
    ok(not re.search(r"^Disallow:\s*/\s*$", pages["/robots.txt"][1], re.M), "robots.txt allows crawling")
    today = datetime.date.today()
    for name, limit in (("reproducibility.json", 45), ("release-watch.json", 45)):
        st, raw = get(base + "/data/" + name + b)
        try:
            checked = datetime.date.fromisoformat(json.loads(raw)["checked"])
            age = (today - checked).days
        except Exception:
            age = 10 ** 6
        if age > 2 * limit:
            ok(False, "%s is %s days old" % (name, age))
            stale = True
        elif age > limit:
            stale = True
            lines.append("- warn %s is %d days old" % (name, age))
        else:
            lines.append("- ok   %s checked %d days ago" % (name, age))
    if stale and os.environ.get("GH_TOKEN"):
        r = subprocess.run(["gh", "workflow", "run", "monthly.yml", "-R", os.environ.get("GITHUB_REPOSITORY", ""), "--ref", "main"],
                           capture_output=True, text=True)
        lines.append("- dispatched monthly.yml: %s" % ("ok" if r.returncode == 0 else r.stderr.strip()[:120]))
    text = "\n".join(lines)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(text + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SITE_URL") or "https://theguysaccount.github.io/democracys-org-democracy-scores"))
