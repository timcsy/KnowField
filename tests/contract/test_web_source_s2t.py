"""契約：`GET /api/source` 的簡→繁顯示層轉換（spec 037，contracts/api-source.md）。

離線注入、零外呼。守衛：儲存層逐字不動（FR-004）、原文可取回（FR-005＋憲章 VI）。
"""
import unittest

from fastapi.testclient import TestClient

from knowfield.ingest.service import ContentIngestService
from knowfield.store.repository import Repository
from knowfield.text import s2t
from tests.web_helpers import build_app, temp_db


class StubEmbedder:
    def embed(self, text):
        return [1.0, 0.0]

    def embed_many(self, texts):
        return [[1.0, 0.0] for _ in texts]


# 簡體正文＋一段承重內容（URL），長度需夠讓 ingest 切塊
_SIMPLIFIED = (
    "# 深入解析Flow Matching技术\n\n"
    + "这个软件的内存管理很复杂，程序员需要学习相关知识。" * 20
    + "\n\n参考 https://a.cn/发展/index.html 说明。\n"
)


def _seed(db, body=_SIMPLIFIED, title="深入解析Flow Matching技术"):
    repo = Repository(db)
    ContentIngestService(repo, StubEmbedder()).ingest_text(body, title=title)
    url = repo.list_source_groups()[0]["url"]
    repo.close()
    return url


class TestSourceS2TContract(unittest.TestCase):
    def test_default_returns_traditional(self):
        """C-002／FR-001／FR-002：預設回繁體，且詞彙在地化。"""
        db = temp_db()
        url = _seed(db)
        d = TestClient(build_app(db)).get(f"/api/source?u={url}").json()
        self.assertTrue(d["found"])
        if s2t.available():
            self.assertIn("軟體", d["markdown"])
            self.assertIn("記憶體", d["markdown"])
            self.assertNotIn("这个软件", d["markdown"])
            self.assertTrue(d["s2t_applied"])
        else:
            self.assertFalse(d["s2t_applied"])

    def test_protected_url_survives(self):
        """FR-006：URL 不得被轉換破壞。"""
        db = temp_db()
        url = _seed(db)
        d = TestClient(build_app(db)).get(f"/api/source?u={url}").json()
        self.assertIn("https://a.cn/发展/index.html", d["markdown"])

    def test_raw_returns_original(self):
        """C-001／FR-005／憲章 VI：raw=1 逐字回原文。"""
        db = temp_db()
        url = _seed(db)
        c = TestClient(build_app(db))
        raw = c.get(f"/api/source?u={url}&raw=1").json()
        self.assertIn("这个软件", raw["markdown"])
        self.assertFalse(raw["s2t_applied"])

    def test_raw_matches_storage_verbatim(self):
        """FR-004：raw 的內容必須與儲存層拼回結果逐字相同。"""
        db = temp_db()
        url = _seed(db)
        raw = TestClient(build_app(db)).get(f"/api/source?u={url}&raw=1").json()["markdown"]
        repo = Repository(db)
        stored = repo.get_source_chunks(url)
        repo.close()
        for chunk in stored:
            core = chunk.replace("<!--kf-page:1-->", "").strip()
            if core:
                self.assertIn(core.split("\n")[0][:20], raw)

    def test_storage_unchanged_after_reads(self):
        """FR-004：讀取（含轉換）不得回寫儲存層。"""
        db = temp_db()
        url = _seed(db)
        repo = Repository(db)
        before = repo.get_source_chunks(url)
        repo.close()
        c = TestClient(build_app(db))
        for _ in range(3):
            c.get(f"/api/source?u={url}")
        repo = Repository(db)
        after = repo.get_source_chunks(url)
        repo.close()
        self.assertEqual(before, after, "顯示層轉換回寫了儲存層——違反 FR-004")

    def test_illegal_raw_value_treated_as_zero(self):
        """C-004：raw 非法值視為 0，不得回錯誤。"""
        db = temp_db()
        url = _seed(db)
        r = TestClient(build_app(db)).get(f"/api/source?u={url}&raw=abc")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["found"])

    def test_existing_fields_unchanged(self):
        """C-005：既有欄位零回歸。"""
        db = temp_db()
        url = _seed(db)
        d = TestClient(build_app(db)).get(f"/api/source?u={url}").json()
        for k in ("found", "url", "title", "markdown", "original_url",
                  "pdf_path", "paper", "note", "ingested_at"):
            self.assertIn(k, d, f"既有欄位消失：{k}")

    def test_engine_unavailable_returns_original_not_error(self):
        """C-003／SC-005：引擎不可用時回 200＋原文，不得 5xx。"""
        db = temp_db()
        url = _seed(db)
        import knowfield.text.s2t as mod
        orig = mod._load_converter
        mod._load_converter = lambda: None
        mod._LOADED = False
        try:
            r = TestClient(build_app(db)).get(f"/api/source?u={url}")
            self.assertEqual(r.status_code, 200)
            d = r.json()
            self.assertFalse(d["s2t_applied"])
            self.assertIn("这个软件", d["markdown"])
        finally:
            mod._load_converter = orig
            mod._LOADED = False
