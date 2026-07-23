"""T008：推與拉皆走散文（情境 A/B）。"""

import unittest

from learnnews.cli.digest_cmd import run_digest
from learnnews.cli.pull_cmd import run_pull
from learnnews.models import InterestProfile
from learnnews.store.repository import Repository
from tests.helpers import FakeAdapter, make_item


class TestArticleBothModes(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(":memory:")
        self.repo.save_interest_profile(InterestProfile(explicit_topics=["agent"]))

    def tearDown(self):
        self.repo.close()

    def test_digest_produces_articles(self):
        item = make_item("agent 規劃", external_id="1", url="https://a/1",
                         abstract="前文。")
        digest = run_digest(self.repo, [FakeAdapter("s", [item])], "2026-07-23")
        self.assertTrue(all(e.article is not None for e in digest.entries))

    def test_pull_produces_articles(self):
        item = make_item("agent 記憶", external_id="2", url="https://a/2",
                         abstract="前文。")
        result = run_pull([FakeAdapter("s", [item])], "agent")
        self.assertTrue(all(e.article is not None for e in result.entries))


if __name__ == "__main__":
    unittest.main()
