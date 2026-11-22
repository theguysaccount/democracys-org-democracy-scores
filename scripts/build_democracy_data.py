#!/usr/bin/env python3
"""Build the public Democracys.org v1 dataset from V-Dem Country-Year Core.

Usage: build_democracy_data.py INPUT.csv PROJECT_DIR [RELEASE.json]

Unchanged from the Democracys.org original except that the V-Dem version, URL, checksum, DOI, attribution and the
latest year come from RELEASE.json (default: release/vdem.json, V-Dem v16) instead of being written in, so a new V-Dem
release can be rebuilt by the scheduled release watch. With the v16 release file the output is byte-identical to the
original script's.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path

RELEASE: dict = {}
WEIGHTS = {
    "electoral": 0.20,
    "liberal": 0.20,
    "participatory": 0.20,
    "deliberative": 0.20,
    "egalitarian": 0.20,
}
VARIABLES = {
    "electoral": "v2x_polyarchy",
    "liberal": "v2x_liberal",
    "participatory": "v2x_partip",
    "deliberative": "v2xdl_delib",
    "egalitarian": "v2x_egal",
}
NAME_OVERRIDES = {
    "USA": "United States",
}


def slugify(value: str) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value


def number(row: dict[str, str], key: str) -> float | None:
    value = row.get(key, "")
    if value == "" or value.upper() == "NA":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def democracy_score(values: dict[str, float]) -> float:
    arithmetic = sum(WEIGHTS[key] * values[key] for key in WEIGHTS)
    if any(values[key] <= 0 for key in WEIGHTS):
        geometric = 0.0
    else:
        geometric = math.exp(sum(WEIGHTS[key] * math.log(values[key]) for key in WEIGHTS))
    return 100 * (0.5 * arithmetic + 0.5 * geometric)


def rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def component_triplet(row: dict[str, str], variable: str) -> tuple[float | None, float | None, float | None]:
    estimate = number(row, variable)
    low = number(row, f"{variable}_codelow")
    high = number(row, f"{variable}_codehigh")
    return estimate, low, high


def main() -> None:
    if len(sys.argv) not in (3, 4):
        raise SystemExit("Usage: build_democracy_data.py INPUT.csv PROJECT_DIR [RELEASE.json]")

    input_path = Path(sys.argv[1]).resolve()
    project_dir = Path(sys.argv[2]).resolve()
    release_path = Path(sys.argv[3]) if len(sys.argv) == 4 else Path(__file__).resolve().parent.parent / "release" / "vdem.json"
    RELEASE.update(json.loads(release_path.read_text(encoding="utf-8")))
    SOURCE_URL, SOURCE_ZIP_SHA256, DATASET_DOI = RELEASE["sourceUrl"], RELEASE["sha256"], RELEASE["doi"]
    version = RELEASE["version"]
    with input_path.open(newline="", encoding="utf-8-sig") as handle:
        latest_year = max(int(row["year"]) for row in csv.DictReader(handle))
    lib_output = project_dir / "lib" / "democracy-data.json"
    public_dir = project_dir / "public" / "data"
    public_json = public_dir / "democracys-score-v1.json"
    public_csv = public_dir / "democracys-score-v1.csv"
    public_readme = public_dir / "README.txt"

    by_code: dict[str, dict] = {}
    active_latest: set[str] = set()

    with input_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            year = int(row["year"])
            code = row["country_text_id"]
            if year == latest_year:
                active_latest.add(code)
            if year < 1900:
                continue

            estimates: dict[str, float] = {}
            lows: dict[str, float] = {}
            highs: dict[str, float] = {}
            missing = False
            for key, variable in VARIABLES.items():
                estimate, low, high = component_triplet(row, variable)
                if estimate is None or low is None or high is None:
                    missing = True
                    break
                estimates[key] = max(0.0, min(1.0, estimate))
                lows[key] = max(0.0, min(1.0, low))
                highs[key] = max(0.0, min(1.0, high))
            if missing:
                continue

            entry = by_code.setdefault(
                code,
                {
                    "id": int(row["country_id"]),
                    "code": code,
                    "cowCode": int(float(row["COWcode"])) if row.get("COWcode") not in (None, "", "NA") else None,
                    "name": NAME_OVERRIDES.get(code, row["country_name"]),
                    "slug": slugify(NAME_OVERRIDES.get(code, row["country_name"])),
                    "history": [],
                },
            )
            point = {
                "year": year,
                "score": rounded(democracy_score(estimates)),
                "lower": rounded(democracy_score(lows)),
                "upper": rounded(democracy_score(highs)),
                "electoral": rounded(estimates["electoral"] * 100),
                "liberal": rounded(estimates["liberal"] * 100),
                "participatory": rounded(estimates["participatory"] * 100),
                "deliberative": rounded(estimates["deliberative"] * 100),
                "egalitarian": rounded(estimates["egalitarian"] * 100),
            }
            entry["history"].append(point)

    countries = [country for code, country in by_code.items() if code in active_latest]
    slugs: dict[str, str] = {}
    for country in countries:
        slug = country["slug"]
        if slug in slugs:
            country["slug"] = f"{slug}-{country['code'].lower()}"
        slugs[country["slug"]] = country["code"]
        country["history"].sort(key=lambda point: point["year"])
        country["firstYear"] = country["history"][0]["year"]
        country["lastYear"] = country["history"][-1]["year"]
        latest = country["history"][-1]
        country["latest"] = latest

    countries.sort(key=lambda country: (-country["latest"]["score"], country["name"]))
    for rank, country in enumerate(countries, start=1):
        country["rank"] = rank
        country["totalRanked"] = len(countries)
        points_by_year = {point["year"]: point for point in country["history"]}
        latest = country["latest"]
        country["weakest"] = min(VARIABLES, key=lambda key: latest[key])
        country["changes"] = {
            str(window): rounded(latest["score"] - points_by_year[latest_year - window]["score"])
            if latest_year - window in points_by_year
            else None
            for window in (1, 5, 10, 25)
        }

    observation_count = sum(len(country["history"]) for country in countries)
    data = {
        "meta": {
            "title": "Democracys Score v1.0 Beta",
            "methodVersion": "1.0-beta",
            "source": RELEASE["label"],
            "sourceUrl": SOURCE_URL,
            "sourceZipSha256": SOURCE_ZIP_SHA256,
            "sourceDoi": DATASET_DOI,
            "sourcePublished": RELEASE["published"],
            "observationYears": [1900, latest_year],
            "generated": RELEASE["generated"],
            "license": "CC BY-SA 4.0",
            "weights": WEIGHTS,
            "formula": "100 × (0.5 × weighted arithmetic mean + 0.5 × weighted geometric mean)",
            "countryCount": len(countries),
            "observationCount": observation_count,
        },
        "countries": countries,
    }

    lib_output.parent.mkdir(parents=True, exist_ok=True)
    public_dir.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    lib_output.write_text(serialized + "\n", encoding="utf-8")
    public_json.write_text(serialized + "\n", encoding="utf-8")

    with public_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow([
            "country", "country_code", "country_slug", "year", "democracys_score",
            "derived_lower", "derived_upper", "electoral", "liberal", "participatory",
            "deliberative", "egalitarian", "method_version", "source_version",
        ])
        for country in sorted(countries, key=lambda item: item["name"]):
            for point in country["history"]:
                writer.writerow([
                    country["name"], country["code"], country["slug"], point["year"],
                    point["score"], point["lower"], point["upper"], point["electoral"],
                    point["liberal"], point["participatory"], point["deliberative"],
                    point["egalitarian"], "1.0-beta", f"V-Dem {version}",
                ])

    readme = f"""DEMOCRACYS SCORE V1.0 BETA

Generated: {RELEASE["generated"]}
Observation period: 1900-{latest_year}
Current countries and territories: {len(countries)}
Country-year observations: {observation_count}

SOURCE
{RELEASE["label"]}, published {RELEASE["publishedLong"]}
{DATASET_DOI}
{SOURCE_URL}
Source ZIP SHA-256: {SOURCE_ZIP_SHA256}

METHOD
Inputs: v2x_polyarchy, v2x_liberal, v2x_partip, v2xdl_delib, v2x_egal.
Weights: 20% each for electoral, liberal, participatory, deliberative, and egalitarian democracy.
The score is 100 times an equal blend of the weighted arithmetic mean and weighted geometric mean.
It is an experimental Democracys.org transformation, not an official V-Dem score or endorsement.
Derived lower and upper values apply the same transformation to V-Dem component bounds; they are an uncertainty envelope, not an independently estimated confidence interval.

LICENSE
The source data and this adapted dataset are distributed under CC BY-SA 4.0.
Attribution: {RELEASE["shortAttribution"]}
"""
    public_readme.write_text(readme, encoding="utf-8")

    digest = hashlib.sha256(public_json.read_bytes()).hexdigest()
    print(json.dumps({
        "countries": len(countries),
        "observations": observation_count,
        "jsonSha256": digest,
        "jsonBytes": public_json.stat().st_size,
        "csvBytes": public_csv.stat().st_size,
    }, indent=2))


if __name__ == "__main__":
    main()
