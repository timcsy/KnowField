"""T019：原文連結 100%（情境 C）＋摘要封頂不代勞（情境 D）。"""

import unittest

from learnnews.cli.digest_cmd import run_digest
from learnnews.models import InterestProfile
from learnnews.store.repository import Repository
from learnnews.summarize.summarizer import count_sentences
from tests.helpers import FakeAdapter, make_item


class TestDigestQuality(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(":memory:")
        self.repo.save_interest_profile(InterestProfile(explicit_topics=["agent"]))

    def tearDown(self):
        self.repo.close()

    def test_every_entry_has_source_link(self):
        items = [
            make_item("agent 規劃框架", external_id="1", url="https://a/1"),
            make_item("多 agent 協作", external_id="2", url="https://a/2"),
        ]
        digest = run_digest(self.repo, [FakeAdapter("s", items)], "2026-07-23")
        self.assertTrue(digest.entries)
        for e in digest.entries:
            self.assertTrue(e.item.url.strip())  # SC-003：100% 有原文連結

    def test_summary_capped_two_sentences(self):
        item = make_item("agent 記憶機制", external_id="3", url="https://a/3")
        digest = run_digest(self.repo, [FakeAdapter("s", [item])], "2026-07-23")
        for e in digest.entries:
            self.assertLessEqual(count_sentences(e.summary.text()), 2)  # SC-004


if __name__ == "__main__":
    unittest.main()
