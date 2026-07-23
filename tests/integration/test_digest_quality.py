"""T019：原文連結 100%（情境 C）＋散文消化（spec 003 後不再封頂）。"""

import unittest

from learnnews.cli.digest_cmd import run_digest
from learnnews.models import InterestProfile
from learnnews.store.repository import Repository
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

    def test_every_entry_has_readable_article(self):
        # spec 003：改為可讀散文（不再封頂於一句定位），每則附一鍵原文
        item = make_item("agent 記憶機制", external_id="3", url="https://a/3",
                         abstract="這是關於 agent 記憶的研究前文。")
        digest = run_digest(self.repo, [FakeAdapter("s", [item])], "2026-07-23")
        for e in digest.entries:
            self.assertIsNotNone(e.article)
            self.assertTrue(e.article.body.strip())
            self.assertEqual(e.article.source_url, e.item.url)  # 一鍵原文


if __name__ == "__main__":
    unittest.main()
