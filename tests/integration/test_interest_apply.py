"""T037：興趣變更套用於匯整（SC-005 的行為面）。"""

import unittest

from learnnews.cli.digest_cmd import run_digest
from learnnews.interests.service import InterestService
from learnnews.store.repository import Repository
from tests.helpers import FakeAdapter, make_item


class TestInterestApply(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(":memory:")
        self.svc = InterestService(self.repo)

    def tearDown(self):
        self.repo.close()

    def test_change_reflects_in_digest(self):
        items = [
            make_item("編譯器 最佳化", external_id="1", url="https://a/1"),
            make_item("agent 規劃", external_id="2", url="https://a/2"),
        ]
        # 只關注 agent → 只留 agent 相關
        self.svc.set(["agent"])
        d1 = run_digest(self.repo, [FakeAdapter("s", items)], "2026-07-23")
        titles = [e.item.title for e in d1.entries]
        self.assertIn("agent 規劃", titles)
        self.assertNotIn("編譯器 最佳化", titles)

        # 改關注編譯器 → 換成編譯器相關
        self.svc.set(["編譯器"])
        items2 = [
            make_item("編譯器 最佳化", external_id="1", url="https://a/1"),
            make_item("agent 規劃", external_id="2", url="https://a/2"),
        ]
        d2 = run_digest(self.repo, [FakeAdapter("s", items2)], "2026-07-23")
        titles2 = [e.item.title for e in d2.entries]
        self.assertIn("編譯器 最佳化", titles2)
        self.assertNotIn("agent 規劃", titles2)


if __name__ == "__main__":
    unittest.main()
