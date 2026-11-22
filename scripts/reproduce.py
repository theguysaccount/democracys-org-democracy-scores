"""Rebuild the published dataset from V-Dem's official file and compare every value.

    python3 scripts/reproduce.py [--today YYYY-MM-DD] [--cache DIR]

Writes data/reproducibility.json. Exits 1 (and records an alert) when the source checksum fails or any value differs by
more than one rounding step; the published data is never changed by this script.
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vdem  # noqa: E402
from report import add_alert, save_step  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--cache")
    args = ap.parse_args(argv)
    release = vdem.read_release()
    with open(os.path.join(vdem.ROOT, "public", "data", "democracys-score-v1.json"), encoding="utf-8") as fh:
        published = json.load(fh)
    result = {"checked": args.today, "release": release["version"], "sourceUrl": release["sourceUrl"],
              "sha256": release["sha256"], "checksum": "unchecked"}
    try:
        csv_path = vdem.download_csv(release, args.cache)
        result["checksum"] = "verified"
        out_dir = vdem.build_into(csv_path)
        with open(os.path.join(out_dir, "democracys-score-v1.json"), encoding="utf-8") as fh:
            rebuilt = json.load(fh)
        cmp = vdem.compare(published, rebuilt)
        result.update({"verdict": vdem.verdict(cmp), "countries": cmp["countries"][0], "rows": cmp["rows"][0],
                       "values": cmp["values"], "exact": cmp["exact"], "max_difference": round(cmp["max_difference"], 3),
                       "differences": cmp["differences"][:200], "differenceCount": len(cmp["differences"]),
                       "missing": cmp["missing"][:50]})
    except Exception as exc:   # download failure, checksum mismatch, build error
        result.update({"verdict": "unverified" if "HTTP" in str(exc) else "failed", "error": str(exc)})
    path = os.path.join(vdem.ROOT, "data", "reproducibility.json")
    previous = json.load(open(path)) if os.path.exists(path) else {}
    if result["verdict"] == "unverified" and previous.get("verdict") in ("exact", "rounding"):
        result = dict(previous, lastAttempt=args.today, lastError=result.get("error"))   # keep the last good check
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    line = "reproducibility (%s): %s" % (release["version"], result["verdict"])
    if result["verdict"] == "failed":
        add_alert("reproducibility", "The published scores no longer reproduce from V-Dem's file",
                  "`scripts/reproduce.py` on %s: %s. The published data was not changed. Check the source checksum and "
                  "the build script." % (args.today, result.get("error") or "%d values differ by more than %.1f" % (
                      result.get("differenceCount", 0), vdem.TOLERANCE)))
    save_step("reproduce", result["verdict"] in ("exact", "rounding", "unverified"), line)
    print(line)
    return 1 if result["verdict"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
