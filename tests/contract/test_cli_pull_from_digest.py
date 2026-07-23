"""T015：`pull --from-digest <rank>`——匯整落庫，拉取讀其主題。"""

import unittest
from argparse import Namespace

from learnnews.cli.pull_cmd import _resolve_topic
from learnnews.models import Digest, DigestEntry
from learnnews.store.repository import Repository
from tests.helpers import make_item


class TestPullFromDigest(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(":memory:")
        # 建一份匯整並落庫（含 matched_topic）
        item = make_item("agent 規劃", external_id="1", url="https://a/1")
        digest = Digest(date="2026-07-23", entries=[
            DigestEntry(item=item, rank=1, relevance_score=0.9, matched_topic="agent")])
        self.repo.save_digest(digest)

    def tearDown(self):
        self.repo.close()

    def test_get_last_digest_entry(self):
        entry = self.repo.get_last_digest_entry(1)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["matched_topic"], "agent")

    def test_resolve_topic_from_digest(self):
        args = Namespace(from_digest=1, topic=None)
        self.assertEqual(_resolve_topic(args, self.repo), "agent")

    def test_resolve_topic_missing_rank(self):
        args = Namespace(from_digest=99, topic=None)
        self.assertIsNone(_resolve_topic(args, self.repo))

    def test_resolve_topic_direct(self):
        args = Namespace(from_digest=None, topic="latent reasoning")
        self.assertEqual(_resolve_topic(args, self.repo), "latent reasoning")


if __name__ == "__main__":
    unittest.main()
