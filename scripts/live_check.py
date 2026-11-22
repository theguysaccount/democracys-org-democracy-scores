"""Is democracys.org still answering, and which V-Dem version does it serve? Records data/live-site.json and raises
'live-down' after 14 days without an answer (then this companion is the only copy online; see OPERATIONS.md)."""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vdem  # noqa: E402
from report import add_alert, save_step  # noqa: E402

LIVE = (os.environ.get("LIVE_URL") or "https://democracys.org").rstrip("/")


def main(today=None):
    today = today or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(vdem.ROOT, "data", "live-site.json")
    prev = json.load(open(path)) if os.path.exists(path) else {}
    status, body = vdem.fetch(LIVE + "/data/democracys-score-v1.json", timeout=60)
    source = None
    if status == 200:
        try:
            source = json.loads(body)["meta"]["source"]
        except Exception:
            source = None
    state = {"checked": today, "url": LIVE, "answering": status == 200, "source": source or prev.get("source"),
             "downSince": None if status == 200 else (prev.get("downSince") or today)}
    with open(path, "w") as fh:
        json.dump(state, fh, indent=1)
        fh.write("\n")
    if state["downSince"] and (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(state["downSince"])).days >= 14:
        add_alert("live-down", "democracys.org has not answered for two weeks",
                  "%s has not served its dataset since %s (last answer: HTTP %s). This companion is still online. If the live site "
                  "is gone for good, set COUNTRY_PAGES_INDEXABLE=true and run deploy.yml (OPERATIONS.md)." % (LIVE, state["downSince"], status))
    save_step("live", True, "democracys.org: %s" % ("answering, serves %s" % source if status == 200 else "no answer (HTTP %s)" % status))
    print(state)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
