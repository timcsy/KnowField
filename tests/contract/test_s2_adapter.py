"""T016：SemanticScholarAdapter 契約，含指數退避。"""

import unittest
from datetime import datetime

from knowfield.sources.base import SourceUnavailable
from knowfield.sources.semantic_scholar import (
    RateLimited,
    SemanticScholarAdapter,
    with_backoff,
)

_SAMPLE = """{"data": [
  {"paperId": "p1", "title": "Scaling Laws", "abstract": "abs",
   "url": "https://www.semanticscholar.org/paper/p1",
   "externalIds": {"ArXiv": "2401.00003"}, "publicationDate": "2026-07-19"}
]}"""


class TestS2Adapter(unittest.TestCase):
    def test_parses_and_prefers_arxiv_id(self):
        a = SemanticScholarAdapter("s2", lambda since: _SAMPLE, sleep=lambda s: None)
        items = a.fetch(datetime(2026, 7, 1))
        self.assertEqual(items[0].external_id, "2401.00003")
        self.assertTrue(items[0].has_source_link())

    def test_backoff_retries_then_succeeds(self):
        calls = {"n": 0}

        def flaky(since):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RateLimited("429")
            return _SAMPLE

        raw = with_backoff(flaky, datetime(2026, 7, 1), sleep=lambda s: None)
        self.assertIn("Scaling Laws", raw)
        self.assertEqual(calls["n"], 3)

    def test_backoff_gives_up_as_unavailable(self):
        def always_limited(since):
            raise RateLimited("429")

        with self.assertRaises(SourceUnavailable):
            with_backoff(always_limited, datetime(2026, 7, 1),
                         max_attempts=2, sleep=lambda s: None)


if __name__ == "__main__":
    unittest.main()
