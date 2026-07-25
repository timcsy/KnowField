"""build 韌性：任何來源例外（非只 SourceUnavailable）都標缺漏、不拖垮整份 digest。"""

import unittest
from datetime import datetime

from learnnews.digest.builder import DigestBuilder
from learnnews.models import Item


class _OkAdapter:
    name = "ok"
    def fetch(self, since):
        return [Item(source_id="ok", external_id="", title="agent 記憶", url="https://a/1",
                     abstract="x")]


class _BoomAdapter:
    name = "boom"
    def fetch(self, since):
        raise ValueError("非 SourceUnavailable 的爆炸")   # 例：解析/型別錯


class TestResilientBuild(unittest.TestCase):
    def test_generic_adapter_exception_marked_missing_not_fatal(self):
        digest = DigestBuilder().build(
            date="2026-07-26", adapters=[_OkAdapter(), _BoomAdapter()],
            explicit_topics=["agent"], with_article=False)
        self.assertIn("boom", digest.missing_sources)         # 壞來源標缺漏
        self.assertTrue(digest.entries)                       # 好來源照常產出（不崩）


if __name__ == "__main__":
    unittest.main()
