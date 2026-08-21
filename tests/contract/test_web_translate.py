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


# ---------------------------------------------------------------- spec 039 ----

def _good_backend(masked: str) -> str:
    """乖乖照抄佔位符的假模型。用它才走得到「翻譯成功」那條路——
    ⚠️ 預設離線後端會讓每一塊都降級（failed == total），而降級是**不快取**的（FR-006），
    所以拿離線後端測快取，測的其實是「什麼都沒發生」。"""
    return "【譯】" + masked


def _app_with_backend(db):
    app = build_app(db)
    app.state.translate_backend_for_test = _good_backend
    return app


class TestTranslationCache(unittest.TestCase):
    """spec 039：譯文落庫。使用者要的是「第二次不用再等」。"""

    def _seed_en(self):
        db = temp_db()
        return db, _seed(db, _EN, "Diffusion Models")

    def test_second_run_is_a_cache_hit(self):
        """US1：翻兩次，第二次直接回快取——沒有任何 stage（進度條不該閃）。"""
        db, en = self._seed_en()
        c = TestClient(_app_with_backend(db))
        first = _sse(c.get(f"/api/source/translate?u={en}"))
        self.assertTrue(any(e == "stage" for e, _ in first), "第一次應該真的在翻")
        second = _sse(c.get(f"/api/source/translate?u={en}"))
        self.assertFalse(any(e == "stage" for e, _ in second), "命中不該送 stage")
        self.assertEqual(second[-1][0], "done")
        self.assertEqual(second[-1][1]["markdown"], first[-1][1]["markdown"])

    def test_cache_hit_does_not_need_the_backend(self):
        """D5：查快取必須排在建後端**之前**——後端掛掉也要拿得到已快取的譯文。
        這條釘的是程式碼順序，不是行為。"""
        db, en = self._seed_en()
        app = _app_with_backend(db)
        c = TestClient(app)
        _sse(c.get(f"/api/source/translate?u={en}"))          # 先種好快取
        # ⚠️ 注入的假後端也要拿掉，否則 `or` 會短路、make_translate_backend 根本不會被呼叫，
        # 這條就變成一次 no-op 的攻擊（撞不到東西的測試不知道自己在測什麼）。
        del app.state.translate_backend_for_test
        import knowfield.backends.factory as _f
        orig = _f.make_translate_backend

        def _boom(_cfg):
            raise RuntimeError("後端不可用")

        _f.make_translate_backend = _boom
        try:
            evs = _sse(c.get(f"/api/source/translate?u={en}"))
        finally:
            _f.make_translate_backend = orig
        self.assertEqual(evs[-1][0], "done")
        self.assertIn("【譯】", evs[-1][1]["markdown"])

    def test_degraded_result_is_not_cached(self):
        """⚠️ FR-006：含降級單位的結果不存——否則那次失敗會被固定下來，
        使用者永遠拿不到完整譯文。用預設離線後端（全降級）跑。"""
        db, en = self._seed_en()
        c = TestClient(build_app(db))                          # 不注入好後端 → 全降級
        done = _sse(c.get(f"/api/source/translate?u={en}"))[-1][1]
        self.assertGreater(done["failed"], 0, "前提：這一跑必須真的有降級")
        repo = Repository(db)
        n = repo.conn.execute(
            "SELECT COUNT(*) AS c FROM translation_units").fetchone()
        repo.close()
        self.assertEqual(int(n["c"]), 0, "降級的單位被存下來了")

    def test_content_change_invalidates_cache(self):
        """FR-004／SC-004：內容變了 → 不得拿到舊譯文，要重新翻。"""
        db, en = self._seed_en()
        c = TestClient(_app_with_backend(db))
        _sse(c.get(f"/api/source/translate?u={en}"))
        repo = Repository(db)     # 模擬「來源被重新收進／編修」——動的是原文塊
        repo.conn.execute(
            "UPDATE digest_entries SET article_body=%s WHERE url=%s",
            (_EN.replace("Gaussian noise", "Totally different noise"), en))
        repo.conn.commit()
        after = repo.get_source_chunks(en)
        repo.close()
        self.assertIn("Totally different noise", "".join(after), "前提：原文真的被改到了")
        evs = _sse(c.get(f"/api/source/translate?u={en}"))
        self.assertTrue(any(e == "stage" for e, _ in evs), "內容變了卻秒回舊譯文")

    def test_original_unchanged_after_caching(self):
        """FR-002／SC-003：落庫的是衍生物，原文逐字不變。

        ⚠️ 上面 spec 038 的 `test_storage_unchanged` **蓋不到這條路**——它用預設離線後端，
        全部降級 ⇒ 根本不會走到落庫那段。實測：把「落庫時順手寫回原文」種進去，
        那條照樣綠、只有這條紅。同一句斷言，換一條路徑就要重寫一次。"""
        db, en = self._seed_en()
        repo = Repository(db); before = repo.get_source_chunks(en); repo.close()
        _sse(TestClient(_app_with_backend(db)).get(f"/api/source/translate?u={en}"))
        repo = Repository(db); after = repo.get_source_chunks(en); repo.close()
        self.assertEqual(before, after)

    def test_partial_failure_keeps_the_good_units(self):
        """⚠️ 這一條是逐單位快取存在的理由。

        真跑（colah 那篇，45 個單位）失敗了 1 個 ⇒ 逐文件快取一個字都不存 ⇒
        使用者要的「自動保存」根本不會發生。機率上 (1-p)^N 讓逐文件快取多半落空，
        這不是運氣差，是結構問題。逐單位：成功的存下、失敗的下次一定重試。
        """
        db, en = self._seed_en()

        def _one_unit_fails(masked: str) -> str:
            if "Gaussian" in masked:
                raise RuntimeError("這一塊翻爆了")
            return "【譯】" + masked

        app = build_app(db)
        app.state.translate_backend_for_test = _one_unit_fails
        c = TestClient(app)
        first = _sse(c.get(f"/api/source/translate?u={en}"))[-1][1]
        self.assertGreater(first["failed"], 0, "前提：這一跑必須真的有降級")
        repo = Repository(db)
        saved = int(repo.conn.execute(
            "SELECT COUNT(*) AS c FROM translation_units").fetchone()["c"])
        repo.close()
        self.assertGreater(saved, 0, "成功的單位陪著失敗的一起被丟掉了")

        # 第二次換成正常後端：只該重翻**失敗過的那些**，不是整篇
        app.state.translate_backend_for_test = _good_backend
        evs = _sse(c.get(f"/api/source/translate?u={en}"))
        stages = [d for e, d in evs if e == "stage"]
        self.assertTrue(stages, "失敗過的單位必須被重試")
        self.assertEqual(stages[-1]["total"], first["failed"],
                         "重翻的量應該剛好等於上次失敗的量")
        self.assertEqual(evs[-1][1]["failed"], 0)
