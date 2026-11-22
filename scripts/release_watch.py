"""Monthly: has V-Dem published a newer Country-Year Core release? If so, rebuild this edition from it.

    python3 scripts/release_watch.py [--today YYYY-MM-DD]

A new release is adopted only when (1) its ZIP downloads, (2) V-Dem's dataset page states its proper citation and DOI
(CC BY-SA attribution must be exact), (3) the rebuilt data passes sanity checks. Then release/vdem.json, public/data/ and
release/history.json are updated and an alert says that democracys.org still shows the older version. Otherwise nothing
changes and data/release-watch.json records what was seen. V-Dem warns that index values must not be compared across
versions, so a new release replaces the whole series instead of appending to it.
"""
import argparse
import datetime
import hashlib
import html
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vdem  # noqa: E402
from report import add_alert, save_step  # noqa: E402

DATASET_PAGE = "https://www.v-dem.net/data/the-v-dem-dataset/"
ZIP = "https://www.v-dem.net/media/datasets/V-Dem-CY-Core-v{n}_csv.zip"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def page_text(markup):
    s = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", markup)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", s)))


def citation_for(text, n):
    """V-Dem's own sentence: 'The proper citation for the vN dataset is: <citation> https://doi.org/...'."""
    m = re.search(r"The proper citation for the v%d dataset is:\s*(.+?(https://doi\.org/10\.23696/\S+?))\s*\.?\s+(?=[A-Z][a-z]+ [a-z]+ [a-z]+|Can I|$)" % n, text)
    if not m:
        return None, None
    return m.group(1).strip().rstrip("."), m.group(2).rstrip(".")


def published_month(text, n):
    m = re.search(r"Version %d Published (%s) (\d{4})" % (n, "|".join(MONTHS)), text)
    if not m:
        return None, None
    return "%s-%02d" % (m.group(2), MONTHS.index(m.group(1)) + 1), "%s %s" % (m.group(1), m.group(2))


def sanity(new, old):
    problems = []
    if len(new["countries"]) < 0.9 * len(old["countries"]):
        problems.append("only %d countries (was %d)" % (len(new["countries"]), len(old["countries"])))
    if new["meta"]["observationYears"][1] < old["meta"]["observationYears"][1]:
        problems.append("latest year went backwards")
    for c in new["countries"]:
        for p in c["history"]:
            if not (0 <= p["score"] <= 100) or not (p["lower"] - 0.15 <= p["score"] <= p["upper"] + 0.15):
                problems.append("%s %s: score %s outside its bounds" % (c["slug"], p["year"], p["score"]))
                break
    return problems[:10]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"))
    args = ap.parse_args(argv)
    release = vdem.read_release()
    current = int(release["version"].lstrip("v"))
    state = {"checked": args.today, "current": release["version"], "found": None, "adopted": False, "note": ""}
    found = None
    for n in (current + 1, current + 2):
        status, _ = vdem.fetch(ZIP.format(n=n), method="HEAD", timeout=60)
        if status == 200:
            found = n
        elif status == 0:
            state["note"] = "v-dem.net did not answer"
    if not found:
        state["note"] = state["note"] or "no release newer than %s" % release["version"]
        return finish(state, True)
    state["found"] = "v%d" % found
    status, body = vdem.fetch(DATASET_PAGE)
    text = page_text(body.decode("utf-8", "replace")) if status == 200 else ""
    citation, doi = citation_for(text, found)
    month, month_long = published_month(text, found)
    if not citation or not doi:
        state["note"] = "v%d is downloadable but V-Dem's dataset page does not state its citation yet; not adopted" % found
        add_alert("vdem-new-release", "V-Dem v%d is out; waiting for its citation" % found,
                  "The ZIP %s answers, but %s does not yet state the proper citation for v%d, which CC BY-SA attribution "
                  "needs. The release watch tries again next month; nothing was changed." % (ZIP.format(n=found), DATASET_PAGE, found))
        return finish(state, True)
    status, blob = vdem.fetch(ZIP.format(n=found))
    if status != 200:
        state["note"] = "download of v%d answered HTTP %s" % (found, status)
        return finish(state, False)
    new_release = dict(release, version="v%d" % found, label="V-Dem Country-Year Core v%d" % found,
                       published=month or args.today[:7], publishedLong=month_long or args.today[:7],
                       sourceUrl=ZIP.format(n=found), sha256=hashlib.sha256(blob).hexdigest(), doi=doi,
                       csvName="V-Dem-CY-Core-v%d.csv" % found, generated=args.today, citation=citation,
                       shortAttribution="Coppedge et al. (%s), V-Dem Country-Year Dataset v%d, Varieties of Democracy Project."
                       % ((month or args.today)[:4], found))
    work = os.path.join(vdem.ROOT, "build", "release")
    os.makedirs(work, exist_ok=True)
    with open(os.path.join(work, os.path.basename(new_release["sourceUrl"])), "wb") as fh:
        fh.write(blob)
    rel_path = os.path.join(work, "vdem.json")
    with open(rel_path, "w", encoding="utf-8") as fh:
        json.dump(new_release, fh, indent=1, ensure_ascii=False)
    try:
        csv_path = vdem.download_csv(new_release, work)
        out_dir = vdem.build_into(csv_path, rel_path)
    except Exception as exc:
        state["note"] = "v%d failed to build: %s" % (found, exc)
        add_alert("vdem-new-release", "V-Dem v%d is out but did not build" % found, state["note"])
        return finish(state, False)
    old = json.load(open(os.path.join(vdem.ROOT, "public", "data", "democracys-score-v1.json"), encoding="utf-8"))
    new = json.load(open(os.path.join(out_dir, "democracys-score-v1.json"), encoding="utf-8"))
    problems = sanity(new, old)
    if problems:
        state["note"] = "v%d rebuilt but failed sanity checks: %s" % (found, "; ".join(problems))
        add_alert("vdem-new-release", "V-Dem v%d is out but the rebuild failed sanity checks" % found, state["note"])
        return finish(state, False)
    for name in os.listdir(out_dir):
        shutil.copy(os.path.join(out_dir, name), os.path.join(vdem.ROOT, "public", "data", name))
    shutil.copy(rel_path, os.path.join(vdem.ROOT, "release", "vdem.json"))
    hist_path = os.path.join(vdem.ROOT, "release", "history.json")
    history = json.load(open(hist_path, encoding="utf-8")) if os.path.exists(hist_path) else []
    history.append({"date": args.today, "version": new_release["version"], "sha256": new_release["sha256"],
                    "countries": len(new["countries"]), "observations": new["meta"]["observationCount"],
                    "years": new["meta"]["observationYears"],
                    "note": "Whole series rebuilt from v%d. V-Dem advises against comparing index values across versions." % found})
    with open(hist_path, "w", encoding="utf-8") as fh:
        json.dump(history, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    state.update(adopted=True, current=new_release["version"], note="adopted v%d" % found)
    add_alert("vdem-newer-than-live", "This edition now shows V-Dem v%d; democracys.org still shows %s" % (found, release["version"]),
              "The release watch rebuilt the whole Democracys Score series from V-Dem v%d (SHA-256 %s, %s). The live site at "
              "democracys.org is unchanged and still shows %s. Update it from public/data/ in this repo, or decide whether "
              "this edition's country pages should become indexable (OPERATIONS.md)." % (found, new_release["sha256"], doi, release["version"]))
    return finish(state, True)


def finish(state, ok):
    with open(os.path.join(vdem.ROOT, "data", "release-watch.json"), "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=1)
        fh.write("\n")
    save_step("release", ok, "V-Dem release watch: %s" % state["note"])
    print(state["note"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
