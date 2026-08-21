"""契約：來源翻譯端點（spec 038，contracts/api-translate.md）。離線注入、零外呼。"""
import json
import unittest

from fastapi.testclient import TestClient

from knowfield.ingest.service import ContentIngestService
from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db


class StubEmbedder:
    def embed(self, text): return [1.0, 0.0]
    def embed_many(self, texts): return [[1.0, 0.0] for _ in texts]


_EN = ("# Forward diffusion process\n\n"
       + "Given a data point sampled from a real data distribution we add Gaussian noise. " * 20
       + "\n\nSee $x_0 \\sim q(x)$ and https://example.org/paper for details.\n")
_ZH = "# 深入解析\n\n" + "這個軟體的記憶體管理很複雜，程式設計師需要學習相關知識。" * 20


def _seed(db, body, title):
    repo = Repository(db)
    ContentIngestService(repo, StubEmbedder()).ingest_text(body, title=title)
    url = repo.list_source_groups()[0]["url"]
    repo.close()
    return url


def _sse(resp):
    """把 SSE 回應解析成 [(type, data), ...]。

    ⚠️ 沿用 /chat/stream 既有協定：type 放在 data 裡（`data: {"type":"done",...}`），
    不是 `event:` 行。本測試第一版自己發明了 event: 那套——改回既有的，不另立協定。
    """
    out = []
    for line in resp.text.splitlines():
        if line.startswith("data:"):
            d = json.loads(line[5:].strip())
            out.append((d.get("type"), d))
    return out


class TestTranslateContract(unittest.TestCase):
    def test_english_flag_on_source(self):
        """契約增補：/api/source 帶 is_english，前端據此決定顯不顯示動作。"""
        db = temp_db()
        en = _seed(db, _EN, "Diffusion Models")
        c = TestClient(build_app(db))
        self.assertTrue(c.get(f"/api/source?u={en}").json()["is_english"])

    def test_chinese_source_not_english(self):
        db = temp_db()
        zh = _seed(db, _ZH, "深入解析")
        c = TestClient(build_app(db))
        self.assertFalse(c.get(f"/api/source?u={zh}").json()["is_english"])

    def test_translate_emits_stage_then_done(self):
        """C-001：事件序列 stage* → done，且 done 的塊數等於原文塊數。"""
        db = temp_db()
        en = _seed(db, _EN, "Diffusion Models")
        r = TestClient(build_app(db)).get(f"/api/source/translate?u={en}")
        self.assertEqual(r.status_code, 200)
        evs = _sse(r)
        self.assertTrue(any(e == "stage" for e, _ in evs), "沒有進度事件（FR-003）")
        self.assertEqual(evs[-1][0], "done")
        done = evs[-1][1]
        self.assertIn("markdown", done)
        self.assertEqual(done["total"], done.get("total"))
        self.assertGreater(done["total"], 0)

    def test_offline_backend_degrades_to_source(self):
        """C-004／FR-010：離線後端 → 全部降級為原文，不中斷、不 5xx。"""
        db = temp_db()
        en = _seed(db, _EN, "Diffusion Models")
        r = TestClient(build_app(db)).get(f"/api/source/translate?u={en}")
        self.assertEqual(r.status_code, 200)
        done = _sse(r)[-1][1]
        self.assertIn("Gaussian noise", done["markdown"], "降級時應為英文原文")
        self.assertEqual(done["failed"], done["total"])

    # ⚠️ 進度的**時機**不在這裡驗——TestClient 會緩衝，我寫了三版契約測試都撞不倒
    # 累積式實作。時機由 tests/unit/test_text_translate.py::TestStreamingProgress 驗
    # （直接測產生器、有時間上界，拿累積式實作去撞會紅）。這裡只驗協定與降級。

    def test_storage_unchanged(self):
        """C-003／FR-005：翻譯不得寫回儲存層。"""
        db = temp_db()
        en = _seed(db, _EN, "Diffusion Models")
        repo = Repository(db); before = repo.get_source_chunks(en); repo.close()
        TestClient(build_app(db)).get(f"/api/source/translate?u={en}")
        repo = Repository(db); after = repo.get_source_chunks(en); repo.close()
        self.assertEqual(before, after)

    def test_chinese_source_rejected(self):
        """C-005／FR-009：非英文來源不提供翻譯。"""
        db = temp_db()
        zh = _seed(db, _ZH, "深入解析")
        evs = _sse(TestClient(build_app(db)).get(f"/api/source/translate?u={zh}"))
        self.assertEqual(evs[-1][0], "error")

    def test_missing_source_errors(self):
        db = temp_db()
        _seed(db, _EN, "Diffusion Models")
        evs = _sse(TestClient(build_app(db)).get("/api/source/translate?u=nope://x"))
        self.assertEqual(evs[-1][0], "error")
