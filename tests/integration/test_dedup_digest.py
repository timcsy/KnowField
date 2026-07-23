"""T018：跨源去重（quickstart 情境 A/B）——同一則跨來源只出現一次。"""

import unittest

from learnnews.cli.digest_cmd import run_digest
from learnnews.models import InterestProfile
from learnnews.store.repository import Repository
from tests.helpers import FakeAdapter, make_item


class TestDedupDigest(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(":memory:")
        self.repo.save_interest_profile(InterestProfile(explicit_topics=["LLM 推理"]))

    def tearDown(self):
        self.repo.close()

    def test_same_paper_from_two_sources_dedup(self):
        # 同一論文（相同 arXiv id）出現在 arXiv 與 HF Papers
        arxiv_item = make_item("LLM 推理 最佳化", external_id="2401.999",
                               url="https://arxiv.org/abs/2401.999")
        hf_item = make_item("LLM 推理 最佳化", external_id="2401.999",
                            url="https://huggingface.co/papers/2401.999")
        digest = run_digest(
            self.repo,
            [FakeAdapter("arxiv", [arxiv_item]), FakeAdapter("hf", [hf_item])],
            "2026-07-23",
        )
        self.assertEqual(len(digest.entries), 1)  # 只出現一次

    def test_distinct_papers_both_present(self):
        a = make_item("LLM 推理 最佳化", external_id="1", url="https://a/1")
        b = make_item("LLM 推理 加速", external_id="2", url="https://a/2")
        digest = run_digest(
            self.repo, [FakeAdapter("s1", [a, b])], "2026-07-23")
        self.assertEqual(len(digest.entries), 2)


if __name__ == "__main__":
    unittest.main()
