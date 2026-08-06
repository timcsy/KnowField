"""spec 032：把一份收進來源整理成候選核心理解（US1 主迴圈＋US2 純度守衛）。

離線 StubExtractor、StubEmbedder，零外呼（教訓 1）。守衛靈魂：整理只產候選、不自動冊封、
收進內容不進 build_field_system_prompt 的地基（原則 6，延續 spec 029 TestPurityGuard）。
"""

import unittest

from knowfield.chat.field_chat import build_field_system_prompt
from knowfield.ingest.activate import distill_source
from knowfield.ingest.service import ContentIngestService
from knowfield.rootcause.extract import Candidate
from knowfield.store.repository import Repository
from tests.rag_helpers import temp_db


class StubEmbedder:
    def embed(self, text):
        return [1.0, 0.0] if "貓" in (text or "") else [0.0, 1.0]

    def embed_many(self, texts):
        return [self.embed(t) for t in texts]


class StubExtractor:
    """離線：回一個固定候選（可指定，如 no_material）。"""
    def __init__(self, cand=None):
        self._cand = cand

    def extract(self, title, body):
        if self._cand is not None:
            return self._cand
        return Candidate(claim=f"根因：{title} 之所以 work 是因為 X",
                         ladder=["表面", "bedrock：資訊理論極限"],
                         touchstones=[{"name": "機制", "passed": True}],
                         fog_flag=False, no_material=False)


def _seed(repo, title="養貓", body=None):
    body = body or ("# 貓\n" + ("貓要吃貓糧與用貓砂很重要。" * 40))
    ContentIngestService(repo, StubEmbedder()).ingest_text(body, title=title)
    return repo.list_source_groups()[0]["url"]


class TestDistillSource(unittest.TestCase):
    def test_creates_candidate_with_source_as_evidence(self):
        repo = Repository(temp_db())
        url = _seed(repo)
        cand = distill_source(repo, StubExtractor(), url, now="2026-08-05")
        self.assertIsNotNone(cand)
        cands = repo.list_why_nodes("candidate")
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0].evidence_urls, [url])   # 源→根因由來＝evidence（教訓 8 零 schema）
        self.assertTrue(cands[0].ladder)                  # 帶 why 階梯
        repo.close()

    def test_no_material_stores_nothing(self):
        repo = Repository(temp_db())
        url = _seed(repo)
        cand = distill_source(repo, StubExtractor(Candidate(no_material=True)), url)
        self.assertIsNone(cand)
        self.assertEqual(repo.list_why_nodes("candidate"), [])   # 挖不到→不硬編（原則 6）
        repo.close()

    def test_empty_source_stores_nothing(self):
        repo = Repository(temp_db())
        self.assertIsNone(distill_source(repo, StubExtractor(), "https://nope/x"))
        self.assertEqual(repo.list_why_nodes("candidate"), [])
        repo.close()

    def test_purity_guard_candidate_only_not_in_base(self):
        """US2：整理只產候選、不自動冊封、收進不進地基。"""
        repo = Repository(temp_db())
        url = _seed(repo, title="超導", body="# 超導\n" + ("室溫超導的機制。" * 40))
        distill_source(repo, StubExtractor(
            Candidate(claim="室溫超導：BCS 電子配對機制", ladder=["表面", "bedrock"],
                      touchstones=[], fog_flag=False)), url, now="2026-08-05")
        self.assertEqual(len(repo.list_why_nodes("candidate")), 1)   # 候選
        self.assertEqual(repo.list_why_nodes("anointed"), [])        # 沒自動冊封
        base = build_field_system_prompt(repo.list_why_nodes("anointed"))
        self.assertNotIn("BCS 電子配對", base)                       # 不進地基
        repo.close()

    def test_source_provenance_after_anoint_and_survives_delete(self):
        repo = Repository(temp_db())
        url = _seed(repo)
        distill_source(repo, StubExtractor(), url, now="2026-08-05")
        wid = repo.list_why_nodes("candidate")[0].id
        repo.anoint_why_node(wid)
        self.assertEqual(repo.why_node_source_provenance().get(wid), url)  # 冊封後連回來源
        repo.delete_source(url)                                     # 來源刪除
        self.assertNotIn(wid, repo.why_node_source_provenance())    # 由來自然消失（優雅，FR-010）
        self.assertEqual(len(repo.list_why_nodes("anointed")), 1)   # 但核心理解仍在（地基不隨來源消失）
        repo.close()


if __name__ == "__main__":
    unittest.main()
