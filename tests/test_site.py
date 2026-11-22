"""The static companion: which pages are indexable, attribution everywhere, complete per-country files."""
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "site"))
import build  # noqa: E402

LIVE = "https://democracys.org"


class Site(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.cfg, cls.data, cls.pages = build.build(os.path.join(cls.tmp, "a"), env={"SITE_URL": "https://example.org/dem", "BUILD_DATE": "2026-11-22"})
        cls.cfg2, _, cls.pages2 = build.build(os.path.join(cls.tmp, "b"), env={"SITE_URL": "https://example.org/dem", "COUNTRY_PAGES_INDEXABLE": "true"})

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def read(self, rel, variant="a"):
        return open(os.path.join(self.tmp, variant, rel), encoding="utf-8").read()

    def test_only_new_pages_are_indexable_by_default(self):
        self.assertEqual(self.pages, ["", "reproducibility/", "embed/"])
        locs = re.findall(r"<loc>(.*?)</loc>", self.read("sitemap.xml"))
        self.assertEqual(locs, ["https://example.org/dem/", "https://example.org/dem/reproducibility/", "https://example.org/dem/embed/"])
        for rel in ("index.html", "reproducibility/index.html", "embed/index.html"):
            self.assertNotIn('content="noindex"', self.read(rel))

    def test_duplicated_pages_defer_to_the_live_site(self):
        for c in self.data["countries"]:
            html = self.read("countries/%s/index.html" % c["slug"])
            self.assertIn('content="noindex"', html)
            self.assertIn('<link rel="canonical" href="%s/countries/%s">' % (LIVE, c["slug"]), html)
            self.assertIn('content="noindex"', self.read("embed/%s/index.html" % c["slug"]))
        self.assertIn('<link rel="canonical" href="%s/rankings">' % LIVE, self.read("rankings/index.html"))

    def test_switch_makes_country_pages_indexable(self):
        self.assertIn("rankings/", self.pages2)
        self.assertEqual(len([p for p in self.pages2 if p.startswith("countries/")]), len(self.data["countries"]))
        html = self.read("countries/%s/index.html" % self.data["countries"][0]["slug"], "b")
        self.assertNotIn('content="noindex"', html)

    def test_vdem_attribution_and_licence_on_every_page(self):
        for root, _, files in os.walk(os.path.join(self.tmp, "a")):
            for f in files:
                if f.endswith(".html") and "404" not in f:
                    text = open(os.path.join(root, f), encoding="utf-8").read()
                    self.assertIn("CC BY-SA 4.0", text, os.path.join(root, f))
                    self.assertRegex(text, r"[Nn]ot an official V-Dem score", os.path.join(root, f))

    def test_full_citation_on_the_data_page(self):
        release = json.load(open(os.path.join(ROOT, "release", "vdem.json")))
        self.assertIn(build.e(release["citation"]), self.read("data/index.html"))

    def test_every_country_has_files_that_match_the_dataset(self):
        for c in self.data["countries"]:
            js = json.loads(self.read("data/countries/%s.json" % c["slug"]))
            self.assertEqual(len(js["country"]["history"]), len(c["history"]))
            lines = self.read("data/countries/%s.csv" % c["slug"]).strip().split("\n")
            self.assertEqual(len(lines), len(c["history"]) + 1)


if __name__ == "__main__":
    unittest.main()
