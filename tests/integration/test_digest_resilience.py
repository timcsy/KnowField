"""T020：來源缺漏不靜默（情境 F）＋空匯整（情境 G）＋無原文者排除。"""

import unittest

from learnnews.cli.digest_cmd import run_digest
from learnnews.models import InterestProfile, Item
from learnnews.store.repository import Repository
from tests.helpers import FakeAdapter, make_item


class TestDigestResilience(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(":memory:")

    def tearDown(self):
        self.repo.close()

    def test_missing_source_recorded_not_silent(self):
        self.repo.save_interest_profile(InterestProfile(explicit_topics=["agent"]))
        good = make_item("agent 規劃", external_id="1", url="https://a/1")
        digest = run_digest(
            self.repo,
            [FakeAdapter("good", [good]), FakeAdapter("flaky", [], fail=True)],
            "2026-07-23",
        )
        self.assertIn("flaky", digest.missing_sources)  # FR-011：明確標示缺漏
        self.assertEqual(len(digest.entries), 1)         # 仍照常產出

    def test_empty_digest_when_no_match(self):
        self.repo.save_interest_profile(InterestProfile(explicit_topics=["量子密碼學"]))
        item = make_item("貓咪攝影日常", external_id="9", url="https://a/9")
        digest = run_digest(self.repo, [FakeAdapter("s", [item])], "2026-07-23")
        self.assertTrue(digest.is_empty)  # 情境 G

    def test_item_without_source_link_excluded(self):
        self.repo.save_interest_profile(InterestProfile(explicit_topics=["agent"]))
        no_link = Item(source_id="s", external_id="10", title="agent 無連結",
                       url="", content_hash="h10")
        good = make_item("agent 有連結", external_id="11", url="https://a/11")
        digest = run_digest(self.repo, [FakeAdapter("s", [no_link, good])], "2026-07-23")
        urls = [e.item.url for e in digest.entries]
        self.assertNotIn("", urls)  # FR-006：無原文者排除
        self.assertIn("https://a/11", urls)


if __name__ == "__main__":
    unittest.main()
