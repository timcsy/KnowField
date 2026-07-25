"""預設名冊擴充：含即時新聞＋社群源、所有源可組 adapter（零網路）。"""

import unittest

from learnnews.cli.fetchers import DEFAULT_SOURCES, build_adapters


class TestDefaultSources(unittest.TestCase):
    def test_has_realtime_and_community_sources(self):
        ids = {s.id for s in DEFAULT_SOURCES}
        # 官方發布＋即時新聞＋社群討論（補論文骨幹＋週刊抓不到的剛紅新聞）
        for sid in ("openai-blog", "techcrunch-ai", "verge-ai", "hn-ai", "reddit-localllama"):
            self.assertIn(sid, ids)
        # 社群/討論源（HN、Reddit）以 blog 類收錄
        by_id = {s.id: s for s in DEFAULT_SOURCES}
        self.assertEqual(by_id["hn-ai"].access_method, "rss")
        self.assertEqual(by_id["reddit-localllama"].type, "blog")

    def test_all_sources_build_adapters(self):
        # 不因新源丟例外；web_search 源（spec 015）無 config/金鑰 → 跳過，其餘全建
        adapters = build_adapters(DEFAULT_SOURCES)
        non_web = [s for s in DEFAULT_SOURCES if s.access_method != "web_search"]
        self.assertEqual(len(adapters), len(non_web))


if __name__ == "__main__":
    unittest.main()
