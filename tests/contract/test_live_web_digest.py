"""T007/T008 [US1/US3/US4]：web adapter 進 digest（流非種子）；失敗→missing。零外部呼叫。"""

import unittest

from learnnews.config import SEEDS_DATE
from learnnews.models import InterestProfile
from learnnews.search.websearch import SearchResult
from learnnews.sources.base import SourceUnavailable
from learnnews.sources.websearch_adapter import WebSearchAdapter
from learnnews.cli.digest_cmd import run_digest
from learnnews.store.repository import Repository
from tests.rag_helpers import temp_db


class _FakeWeb:
    def __init__(self, results): self._r = results
    def search(self, q, *, news=False, time_range=None): return list(self._r)


class _BoomWeb:
    def search(self, q, *, news=False, time_range=None): raise SourceUnavailable("搜尋掛了")


class TestLiveWebDigest(unittest.TestCase):
    def _repo_with_interest(self, topic):
        repo = Repository(temp_db())
        repo.save_interest_profile(InterestProfile(explicit_topics=[topic], learned_weights={}))
        return repo

    def test_web_material_enters_digest_as_flow_not_seed(self):
        repo = self._repo_with_interest("agent memory")
        web = WebSearchAdapter("web-ai-trends", _FakeWeb([
            SearchResult("agent memory 突破", "https://news/opus5", "新模型發布"),
            SearchResult("agent memory 心得", "https://news/opus5", "重複 url"),   # 去重
        ]), ["latest AI"])
        digest = run_digest(repo, [web], date="2026-07-25", limit=10)
        urls = [e.item.url for e in digest.entries]
        self.assertIn("https://news/opus5", urls)             # web 材料進了匯整
        self.assertEqual(urls.count("https://news/opus5"), 1)  # 去重

        repo.save_digest(digest)                              # 落庫（run_digest 只 build）
        # web 材料在流（真實匯整），不在種子容器
        rows = repo.conn.execute(
            "SELECT d.date FROM digest_entries de JOIN digests d ON de.digest_id=d.id"
            " WHERE de.url=?", ("https://news/opus5",)).fetchall()
        self.assertTrue(rows and all(r["date"] != SEEDS_DATE for r in rows))
        # 種子容器沒有它
        self.assertEqual(repo.list_seeds(), [])
        repo.close()

    def test_web_search_failure_marks_missing_digest_continues(self):
        repo = self._repo_with_interest("agent")
        ok = WebSearchAdapter("web-ai-trends", _FakeWeb([
            SearchResult("agent 記憶", "https://a/ok", "s")]), ["q"])
        boom = WebSearchAdapter("web-boom", _BoomWeb(), ["q"])
        digest = run_digest(repo, [ok, boom], date="2026-07-25", limit=10)
        self.assertIn("web-boom", digest.missing_sources)     # 失敗源標缺漏
        self.assertTrue(digest.entries)                       # 匯整照常產出
        repo.close()


if __name__ == "__main__":
    unittest.main()
