"""spec 020：場驅動來源推薦——純函式 recommend_sources。

複用 spec 008 feed 探測/驗證＋005/018 嵌入相近。涵蓋：
- 死/幻覺 feed 濾除、無 feed 標示、list_hits 計數（T002）
- 場驅動排序（場驅動 ＞ 有活 feed ＞ 跨清單）＋無 attractor 退回（T003）
- 已訂閱標示（T004）
"""

import unittest

from learnnews.models import Article, Item, Source
from learnnews.search.websearch import SearchResult
from learnnews.sources.recommend import recommend_sources
from learnnews.store.repository import Repository
from tests.rag_helpers import temp_db

# --- 假 feed 內容 ---
_RSS = ('<?xml version="1.0"?><rss><channel><title>{name}</title>'
        '<item><title>一則</title><link>https://{d}/a</link></item></channel></rss>')
_RSS_EMPTY = ('<?xml version="1.0"?><rss><channel><title>Dead</title></channel></rss>')
_HTML_WITH_FEED = ('<html><head><link rel="alternate" type="application/rss+xml" '
                   'href="/feed"></head><body>x</body></html>')
_HTML_NO_FEED = '<html><head><title>No Feed</title></head><body>x</body></html>'


def _http_get(url):
    """foo=活 feed（首頁即 feed）；dead=探到 feed 但空（幻覺）；nofeed=無 feed。"""
    if url == "https://foo.com/":
        return _RSS.format(name="Foo Blog", d="foo.com")
    if url == "https://dead.com/":
        return _HTML_WITH_FEED
    if url == "https://dead.com/feed":
        return _RSS_EMPTY
    if url == "https://nofeed.com/":
        return _HTML_NO_FEED
    raise ValueError(f"未預期的抓取：{url}")


class _KwEmbedder:
    """含 MATCH → [1,0]，否則 [0,1]（令帶 MATCH 的候選與帶 MATCH 的種子相近）。"""
    dim = 2

    def embed(self, text):
        return [1.0, 0.0] if "MATCH" in (text or "") else [0.0, 1.0]

    def embed_many(self, texts):
        return [self.embed(t) for t in texts]


class _FakeWebSearch:
    def __init__(self, results, sink=None):
        self._results = results
        self._sink = sink

    def search(self, query, *, news=False, time_range=None):
        if self._sink is not None:
            self._sink.append(news)          # 記錄 news 參數（應為 False）
        return self._results


def _seed_match(repo):
    repo.ingest_seed(Item(source_id="s", external_id="", title="MATCH 種子",
                          url="https://foo.com/orig"),
                     Article(item_id=0, body="MATCH 這是你冊封的東西",
                             source_url="https://foo.com/orig", headline="MATCH 種子"))


class TestRecommendSources(unittest.TestCase):
    def _results(self):
        # foo 跨兩筆重複（list_hits=2）；dead、nofeed 各一
        return [
            SearchResult("Foo", "https://foo.com/x", "MATCH 很棒的 AI 部落格"),
            SearchResult("Foo again", "https://foo.com/y", "MATCH 再次出現"),
            SearchResult("Dead", "https://dead.com/z", "看似有 feed 其實空"),
            SearchResult("NoFeed", "https://nofeed.com/z", "好站但沒 RSS"),
        ]

    def test_dead_feed_filtered_nofeed_marked_listhits(self):        # T002
        repo = Repository(temp_db())
        _seed_match(repo)
        out = recommend_sources(_FakeWebSearch(self._results()), _KwEmbedder(),
                                 repo, http_get=_http_get, queries=["找 AI 部落格"])
        by_dom = {c.domain: c for c in out}
        self.assertNotIn("dead.com", by_dom)               # 幻覺/空 feed 被擋
        self.assertIn("foo.com", by_dom)
        self.assertTrue(by_dom["foo.com"].has_feed)
        self.assertIn("nofeed.com", by_dom)                # 無 feed 仍保留
        self.assertFalse(by_dom["nofeed.com"].has_feed)    # 但標示不可訂
        self.assertEqual(by_dom["foo.com"].list_hits, 2)   # 跨結果重複計數
        repo.close()

    def test_field_driven_sort(self):                                # T003
        repo = Repository(temp_db())
        _seed_match(repo)
        out = recommend_sources(_FakeWebSearch(self._results()), _KwEmbedder(),
                                 repo, http_get=_http_get)
        # foo：場驅動高＋有 feed → 排第一
        self.assertEqual(out[0].domain, "foo.com")
        self.assertGreater(out[0].field_score, out[1].field_score)

    def test_no_attractor_still_lists(self):                         # T003
        repo = Repository(temp_db())            # 空場，無種子/根因
        out = recommend_sources(_FakeWebSearch(self._results()), _KwEmbedder(),
                                 repo, http_get=_http_get)
        doms = [c.domain for c in out]
        self.assertIn("foo.com", doms)                     # 仍出清單
        # 無 attractor → 場分數全 0，有 feed 者（foo）排在無 feed（nofeed）前
        self.assertLess(doms.index("foo.com"), doms.index("nofeed.com"))
        repo.close()

    def test_already_subscribed_marked(self):                        # T004
        repo = Repository(temp_db())
        _seed_match(repo)
        repo.upsert_source(Source(id="sub-foo-com", name="Foo Blog", type="blog",
                                  access_method="rss", endpoint="https://foo.com/",
                                  enabled=True))
        out = recommend_sources(_FakeWebSearch(self._results()), _KwEmbedder(),
                                 repo, http_get=_http_get)
        foo = next(c for c in out if c.domain == "foo.com")
        self.assertTrue(foo.already_subscribed)
        repo.close()

    def test_search_uses_general_not_news(self):                     # 護城河：一般搜尋非 news
        repo = Repository(temp_db())
        sink = []
        recommend_sources(_FakeWebSearch(self._results(), sink), _KwEmbedder(),
                          repo, http_get=_http_get, queries=["找部落格"])
        self.assertEqual(sink, [False])                    # news=False
        repo.close()


if __name__ == "__main__":
    unittest.main()
