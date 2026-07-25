"""T005/T006 [US2]：build_adapters 金鑰閘（web_search 建/跳）；預設源停用；_parse_queries。"""

import unittest

from learnnews.config import Config
from learnnews.cli.fetchers import DEFAULT_SOURCES, _parse_queries, build_adapters
from learnnews.models import Source
from learnnews.sources.websearch_adapter import WebSearchAdapter

_WEB = Source("web-ai-trends", "開放網路 AI 趨勢", "news", "web_search",
              "latest AI\nnew LLM", enabled=False)


class TestBuildAdaptersWeb(unittest.TestCase):
    def _cfg(self, key=False):
        c = Config.from_env()
        c.search_api_url = "https://api.tavily.com/search" if key else ""
        c.search_api_key = "k" if key else ""
        return c

    def test_web_source_needs_key_and_config(self):
        # 無 config → 跳過（pull 情境）
        self.assertFalse(any(isinstance(a, WebSearchAdapter)
                             for a in build_adapters([_WEB])))
        # 有 config 無金鑰 → 跳過（FR-003）
        self.assertFalse(any(isinstance(a, WebSearchAdapter)
                             for a in build_adapters([_WEB], self._cfg(key=False))))
        # 有 config＋金鑰 → 建 web adapter
        adapters = build_adapters([_WEB], self._cfg(key=True))
        self.assertTrue(any(isinstance(a, WebSearchAdapter) for a in adapters))

    def test_default_source_present_and_disabled(self):
        by_id = {s.id: s for s in DEFAULT_SOURCES}
        self.assertIn("web-ai-trends", by_id)
        self.assertFalse(by_id["web-ai-trends"].enabled)     # 預設停用（opt-in）
        self.assertEqual(by_id["web-ai-trends"].access_method, "web_search")

    def test_parse_queries(self):
        self.assertEqual(_parse_queries("a\nb\n c "), ["a", "b", "c"])
        self.assertEqual(_parse_queries("x, y ,z"), ["x", "y", "z"])
        self.assertEqual(_parse_queries("  "), [])


if __name__ == "__main__":
    unittest.main()
