"""T015：HFPapersAdapter 契約。"""

import unittest
from datetime import datetime

from knowfield.sources.hf_papers import HFPapersAdapter
from knowfield.sources.base import SourceUnavailable

_SAMPLE = """[
  {"paper": {"id": "2401.00002", "title": "Agentic Planning",
             "summary": "A study of agents.", "publishedAt": "2026-07-21T00:00:00Z"}}
]"""


class TestHFAdapter(unittest.TestCase):
    def test_parses(self):
        a = HFPapersAdapter("hf", lambda since: _SAMPLE)
        items = a.fetch(datetime(2026, 7, 1))
        self.assertEqual(items[0].external_id, "2401.00002")
        self.assertTrue(items[0].url.endswith("2401.00002"))
        self.assertTrue(items[0].has_source_link())

    def test_bad_json_raises(self):
        a = HFPapersAdapter("hf", lambda since: "not json")
        with self.assertRaises(SourceUnavailable):
            a.fetch(datetime(2026, 7, 1))


if __name__ == "__main__":
    unittest.main()
