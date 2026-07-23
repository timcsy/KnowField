"""T009：優雅降級（情境 H）——散文後端失敗退精簡、不炸、退出碼 0。"""

import unittest

from learnnews.backends.openai_api import OpenAIError
from learnnews.cli.pull_cmd import run_pull
from learnnews.pull.service import PullService
from learnnews.summarize.article import ArticleBuilder
from tests.helpers import FakeAdapter, make_item


class _FailBackend:
    def write_article(self, title, abstract, matched_topic):
        raise OpenAIError("模擬後端失敗")


class TestArticleDegrade(unittest.TestCase):
    def test_backend_failure_degrades_not_crash(self):
        svc = PullService(article_builder=ArticleBuilder(backend=_FailBackend()))
        item = make_item("agent 規劃", external_id="1", url="https://a/1")
        # 不應拋例外
        result = run_pull([FakeAdapter("s", [item])], "agent", service=svc)
        self.assertFalse(result.is_empty)
        a = result.entries[0].article
        self.assertTrue(a.degraded)                 # 標示降級
        self.assertEqual(a.source_url, "https://a/1")  # 仍保留原礦連結


if __name__ == "__main__":
    unittest.main()
