"""T011/T015-T017：閉環（冊封根因→ask 檢索）＋web 冊封/退回。

注：自種子萃取根因（/whynode/extract）已隨新聞分診子系統退役（history/068），
其對應測試一併移除；保留 ask 檢索閉環與人閘門冊封/移除。
"""

import unittest

from fastapi.testclient import TestClient

from knowfield.rag.service import RagService
from knowfield.ranking.embeddings import HashingEmbedder
from knowfield.rag.answerer import StubAnswerer
from knowfield.store.repository import Repository
from tests.rag_helpers import temp_db
from tests.web_helpers import build_app


class TestClosedLoop(unittest.TestCase):
    def test_anointed_why_node_retrieved_by_ask(self):
        # US3 閉環：冊封一個根因（claim 含關鍵詞）→ RagService 檢索得到、sources 含其證據
        db = temp_db()
        repo = Repository(db)
        wid = repo.add_why_node(
            claim="transformer attention 有效的根因是直接建模長程依賴",
            evidence_urls=["https://root/evidence"], touchstones=[], fog_flag=False,
            source_entry_id=1, created_at="2026-07-25")
        repo.anoint_why_node(wid)

        svc = RagService(repo, HashingEmbedder(), StubAnswerer(),
                         min_score=0.02, root_weight=2.0)
        ans = svc.answer("attention 長程依賴")
        self.assertFalse(ans.no_material)
        self.assertIn("https://root/evidence", [s.url for s in ans.sources])  # 檢索到根因
        repo.close()


if __name__ == "__main__":
    unittest.main()
