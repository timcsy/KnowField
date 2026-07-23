"""T022：--raw 純原礦、無散文無圖、未呼叫生成後端。"""

import unittest

from learnnews.backends.openai_api import OpenAIError
from learnnews.cli.digest_cmd import run_digest
from learnnews.cli.pull_cmd import run_pull
from learnnews.cli.pull_render import render
from learnnews.digest.builder import DigestBuilder
from learnnews.models import InterestProfile
from learnnews.pull.service import PullService
from learnnews.summarize.article import ArticleBuilder
from learnnews.store.repository import Repository
from tests.helpers import FakeAdapter, make_item


class _ExplodeBackend:
    """若被呼叫就爆——用來證明 --raw 完全不呼叫生成後端。"""
    def write_article(self, title, abstract, matched_topic):
        raise OpenAIError("不該被呼叫")


class TestRawPreserved(unittest.TestCase):
    def test_pull_raw_no_article_no_backend_call(self):
        svc = PullService(article_builder=ArticleBuilder(backend=_ExplodeBackend()))
        item = make_item("agent", external_id="1", url="https://a/1")
        # --raw：with_summary=False → 不應觸發後端（否則 _ExplodeBackend 會使 degraded）
        result = run_pull([FakeAdapter("s", [item])], "agent",
                          with_summary=False, service=svc)
        self.assertIsNone(result.entries[0].article)
        out = render(result, "terminal", raw=True)
        self.assertIn("原文：", out)
        self.assertIn("agent", out)

    def test_digest_raw_no_article_no_backend_call(self):
        repo = Repository(":memory:")
        repo.save_interest_profile(InterestProfile(explicit_topics=["agent"]))
        builder = DigestBuilder(article_builder=ArticleBuilder(backend=_ExplodeBackend()))
        item = make_item("agent 規劃", external_id="1", url="https://a/1")
        digest = run_digest(repo, [FakeAdapter("s", [item])], "2026-07-23",
                            builder=builder, with_summary=False)
        self.assertTrue(all(e.article is None for e in digest.entries))
        repo.close()


if __name__ == "__main__":
    unittest.main()
