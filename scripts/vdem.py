"""Shared helpers: polite HTTP, the V-Dem download, and comparing two builds of the dataset. Standard library only."""
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_URL = "https://github.com/theguysaccount/democracys-org-democracy-scores"
UA = "democracys-org-democracy-scores/1.0 (+%s)" % REPO_URL
TOLERANCE = 0.1   # one rounding step of the published one-decimal values


def fetch(url, method="GET", timeout=120, tries=3):
    """(status, bytes) with retries; status 0 means no HTTP answer."""
    last = (0, b"")
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, (resp.read() if method == "GET" else b"")
        except urllib.error.HTTPError as exc:
            last = (exc.code, b"")
            if exc.code not in (429, 500, 502, 503, 504):
                return last
        except Exception:
            last = (0, b"")
        time.sleep(5 * (attempt + 1))
    return last


def read_release(path=None):
    with open(path or os.path.join(ROOT, "release", "vdem.json"), encoding="utf-8") as fh:
        return json.load(fh)


def download_csv(release, cache_dir=None):
    """Download the release ZIP, verify its SHA-256, return the path of the extracted CSV. Raises on mismatch."""
    cache_dir = cache_dir or tempfile.mkdtemp(prefix="vdem-")
    zpath = os.path.join(cache_dir, os.path.basename(release["sourceUrl"]))
    if not os.path.exists(zpath):
        status, body = fetch(release["sourceUrl"])
        if status != 200 or not body:
            raise RuntimeError("V-Dem download answered HTTP %s" % status)
        with open(zpath, "wb") as fh:
            fh.write(body)
    digest = hashlib.sha256(open(zpath, "rb").read()).hexdigest()
    if digest != release["sha256"]:
        raise RuntimeError("SHA-256 mismatch: expected %s, got %s" % (release["sha256"], digest))
    with zipfile.ZipFile(zpath) as zf:
        zf.extract(release["csvName"], cache_dir)
    return os.path.join(cache_dir, release["csvName"])


def build_into(csv_path, release_path=None):
    """Run the build script into a temporary project; return the path of its public/data directory."""
    out = tempfile.mkdtemp(prefix="democracys-build-")
    args = [sys.executable, os.path.join(ROOT, "scripts", "build_democracy_data.py"), csv_path, out]
    if release_path:
        args.append(release_path)
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)
    return os.path.join(out, "public", "data")


FIELDS = ("score", "lower", "upper", "electoral", "liberal", "participatory", "deliberative", "egalitarian")


def compare(published, rebuilt):
    """Value-by-value comparison of two dataset dicts. Never raises."""
    out = {"countries": [len(published["countries"]), len(rebuilt["countries"])], "rows": [0, 0], "values": 0,
           "exact": 0, "differences": [], "max_difference": 0.0, "missing": []}
    rb = {c["slug"]: c for c in rebuilt["countries"]}
    for c in published["countries"]:
        out["rows"][0] += len(c["history"])
        other = rb.get(c["slug"])
        if not other:
            out["missing"].append(c["slug"])
            continue
        by_year = {p["year"]: p for p in other["history"]}
        for p in c["history"]:
            q = by_year.get(p["year"])
            if q is None:
                out["missing"].append("%s %s" % (c["slug"], p["year"]))
                continue
            for f in FIELDS:
                out["values"] += 1
                a, b = p.get(f), q.get(f)
                if a == b:
                    out["exact"] += 1
                    continue
                diff = abs((a or 0) - (b or 0)) if a is not None and b is not None else float("inf")
                out["max_difference"] = max(out["max_difference"], diff)
                out["differences"].append({"country": c["name"], "slug": c["slug"], "year": p["year"], "field": f,
                                           "published": a, "rebuilt": b})
    out["rows"][1] = sum(len(c["history"]) for c in rebuilt["countries"])
    return out


def verdict(cmp):
    if cmp["missing"] or cmp["countries"][0] != cmp["countries"][1] or cmp["rows"][0] != cmp["rows"][1]:
        return "failed"
    if cmp["max_difference"] > TOLERANCE + 1e-9:
        return "failed"
    return "exact" if not cmp["differences"] else "rounding"
