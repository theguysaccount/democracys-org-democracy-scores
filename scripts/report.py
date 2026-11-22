"""refresh-report.json: steps that ran and alerts for scripts/alerts.py to turn into ops-alert issues."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "refresh-report.json")


def _read():
    if os.path.exists(REPORT):
        with open(REPORT, encoding="utf-8") as fh:
            return json.load(fh)
    return {"steps": {}, "alerts": [], "lines": []}


def _write(r):
    with open(REPORT, "w", encoding="utf-8") as fh:
        json.dump(r, fh, indent=1, ensure_ascii=False)


def add_alert(key, title, body):
    r = _read()
    r["alerts"] = [a for a in r["alerts"] if a["key"] != key] + [{"key": key, "title": title, "body": body}]
    _write(r)
    if os.environ.get("GITHUB_ACTIONS"):
        print("::warning::%s" % title)


def save_step(step, ok, line=""):
    r = _read()
    r["steps"][step] = bool(ok)
    if line:
        r["lines"].append(line)
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write("- %s\n" % line)
    _write(r)
