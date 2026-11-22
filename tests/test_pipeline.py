"""The data pipeline: the build script on a small V-Dem-shaped file, the comparison, and the release watch's parsing."""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "tests", "fixtures")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import release_watch  # noqa: E402
import vdem  # noqa: E402


class BuildScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.mkdtemp()
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_democracy_data.py"), os.path.join(FIX, "vdem-mini.csv"),
                        cls.out, os.path.join(FIX, "release-mini.json")], check=True, stdout=subprocess.DEVNULL)
        with open(os.path.join(cls.out, "public", "data", "democracys-score-v1.json")) as fh:
            cls.data = json.load(fh)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.out, ignore_errors=True)

    def test_latest_year_and_active_countries_come_from_the_file(self):
        self.assertEqual(self.data["meta"]["observationYears"], [1900, 2026])
        self.assertEqual(sorted(c["code"] for c in self.data["countries"]), ["GAP", "TST"])   # OLD stopped in 1990

    def test_formula(self):
        p = self.data["countries"][0]["history"][-1]
        comps = [p[f] / 100 for f in ("electoral", "liberal", "participatory", "deliberative", "egalitarian")]
        arith = sum(0.2 * v for v in comps)
        geo = math.exp(sum(0.2 * math.log(v) for v in comps))
        self.assertAlmostEqual(p["score"], 100 * (0.5 * arith + 0.5 * geo), delta=0.11)
        self.assertLessEqual(p["lower"], p["score"] + 0.1)
        self.assertGreaterEqual(p["upper"], p["score"] - 0.1)

    def test_years_without_data_are_skipped(self):
        gap = [c for c in self.data["countries"] if c["code"] == "GAP"][0]
        self.assertNotIn(1942, [p["year"] for p in gap["history"]])

    def test_release_metadata_flows_into_every_file(self):
        self.assertEqual(self.data["meta"]["source"], "V-Dem Country-Year Core v99")
        csv_text = open(os.path.join(self.out, "public", "data", "democracys-score-v1.csv")).read()
        self.assertIn(",V-Dem v99\n", csv_text)
        readme = open(os.path.join(self.out, "public", "data", "README.txt")).read()
        self.assertIn("V-Dem Country-Year Dataset v99", readme)
        self.assertIn("Observation period: 1900-2026", readme)

    def test_changes_are_relative_to_the_latest_year(self):
        c = [c for c in self.data["countries"] if c["code"] == "TST"][0]
        by = {p["year"]: p for p in c["history"]}
        self.assertAlmostEqual(c["changes"]["10"], round(by[2026]["score"] - by[2016]["score"], 1), delta=0.11)


class Compare(unittest.TestCase):
    def ds(self, value):
        return {"countries": [{"slug": "a", "name": "A", "history": [{"year": 2000, "score": value, "lower": 1, "upper": 2, "electoral": 1,
                                                                        "liberal": 1, "participatory": 1, "deliberative": 1, "egalitarian": 1}]}]}

    def test_verdicts(self):
        self.assertEqual(vdem.verdict(vdem.compare(self.ds(50.0), self.ds(50.0))), "exact")
        self.assertEqual(vdem.verdict(vdem.compare(self.ds(50.0), self.ds(50.1))), "rounding")
        self.assertEqual(vdem.verdict(vdem.compare(self.ds(50.0), self.ds(50.3))), "failed")
        missing = {"countries": []}
        self.assertEqual(vdem.verdict(vdem.compare(self.ds(50.0), missing)), "failed")


class ReleaseWatch(unittest.TestCase):
    def test_reads_vdems_own_citation_sentence(self):
        text = release_watch.page_text(open(os.path.join(FIX, "vdem-page.html")).read())
        citation, doi = release_watch.citation_for(text, 17)
        self.assertEqual(doi, "https://doi.org/10.23696/vdemds27")
        self.assertTrue(citation.startswith("Coppedge, Michael"))
        self.assertIn("Dataset v17", citation)
        self.assertEqual(release_watch.published_month(text, 17), ("2027-03", "March 2027"))
        self.assertEqual(release_watch.citation_for(text, 18), (None, None))

    def test_sanity_rejects_a_shrunken_or_inconsistent_release(self):
        old = {"meta": {"observationYears": [1900, 2025]}, "countries": [{}] * 100}
        ok = {"meta": {"observationYears": [1900, 2026]}, "countries": [{"slug": "x", "history": [{"year": 2026, "score": 50, "lower": 45, "upper": 55}]}] * 100}
        self.assertEqual(release_watch.sanity(ok, old), [])
        small = dict(ok, countries=ok["countries"][:50])
        self.assertTrue(release_watch.sanity(small, old))
        bad = {"meta": {"observationYears": [1900, 2026]}, "countries": [{"slug": "x", "history": [{"year": 2026, "score": 60, "lower": 45, "upper": 55}]}] * 100}
        self.assertTrue(release_watch.sanity(bad, old))


if __name__ == "__main__":
    unittest.main()
