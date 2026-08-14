"""spec 033：/api 基座——共用既有服務、行為與舊 /chat 一致。離線注入替身，零外呼（教訓 1）。

守衛靈魂：人閘門（唯 /api/chat/anoint 寫地基）＋純度（stream/distill 不寫地基）＋溯源（結構化來源）。
"""

import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


class StubChat:
    """chat_backend 替身：reply 回固定字串；stream 逐段吐（含 [1]）。"""
    def __init__(self, text="室溫超導靠電子配對 [1]。"):
        self.text = text

    def reply(self, messages):
        return self.text

    def stream(self, messages):
        yield self.text[:4]
        yield self.text[4:]


def _corpus(*items):
    return lambda q: [SimpleNamespace(title=t, snippet=s, url=u, kind="corpus")
                      for t, s, u in items]


class TestApiChat(unittest.TestCase):
    def test_state_shape(self):
        app = build_app(temp_db())
        r = TestClient(app).get("/api/chat/state").json()
        self.assertIn("root_count", r)
        self.assertIn("recent_temp", r)
        self.assertEqual(r["root_count"], 0)

    def test_stream_sse_with_structured_sources(self):
        app = build_app(temp_db())
        app.state.chat_backend_for_test = StubChat("室溫超導靠電子配對 [1]。")
        app.state.chat_search_for_test = lambda q: []
        app.state.corpus_search_for_test = _corpus(("超導文", "電子配對", "https://a/1"))
        text = TestClient(app).post(
            "/api/chat/stream",
            json={"history": [], "message": "超導為何 work", "bare": False}).text
        self.assertIn("data:", text)          # SSE
        self.assertIn("token", text)          # 逐字
        self.assertIn("done", text)           # 完成
        self.assertIn("corpus", text)         # 你收藏的＝結構化來源（原則 3 溯源靠結構）

    def test_stream_bare_skips_search(self):
        app = build_app(temp_db())
        app.state.chat_backend_for_test = StubChat("純發想。")
        spy = []
        app.state.corpus_search_for_test = lambda q: (spy.append(q) or [])
        TestClient(app).post("/api/chat/stream",
                             json={"history": [], "message": "隨便聊", "bare": True}).text
        self.assertEqual(spy, [])             # 腦力激盪不撒網（沙盒，原則 6）

    def test_done_marks_length_truncation(self):
        """撞 max_tokens 被切 → done 帶 truncated=length（否則靜默半句、看起來像講完了）。"""
        class _Cut:
            def reply(self, m): return "半截"
            def stream(self, m):
                yield "被切一半"
                return "length"
        app = build_app(temp_db())
        app.state.chat_backend_for_test = _Cut()
        text = TestClient(app).post(
            "/api/chat/stream", json={"history": [], "message": "問", "bare": True}).text
        self.assertIn('"truncated": "length"', text)
        self.assertIn("被切一半", text)

    def test_midstream_break_keeps_partial_and_marks(self):
        """中途斷線 → 保留已收到的字＋標 connection，而不是整條 SSE 裸死。"""
        class _Drop:
            def reply(self, m): return "x"
            def stream(self, m):
                yield "已經講到一半"
                raise ConnectionResetError("斷了")
        app = build_app(temp_db())
        app.state.chat_backend_for_test = _Drop()
        text = TestClient(app).post(
            "/api/chat/stream", json={"history": [], "message": "問", "bare": True}).text
        self.assertIn("已經講到一半", text)                 # 已收到的不丟
        self.assertIn('"truncated": "connection"', text)
        self.assertIn('"type": "done"', text)

    def test_failure_before_any_token_is_error_event(self):
        """一個字都沒吐就失敗 → error 事件（沒有半截可留），且不是未攔的例外。"""
        class _Dead:
            def reply(self, m): return "x"
            def stream(self, m):
                raise ConnectionResetError("一開始就斷")
                yield  # pragma: no cover
        app = build_app(temp_db())
        app.state.chat_backend_for_test = _Dead()
        text = TestClient(app).post(
            "/api/chat/stream", json={"history": [], "message": "問", "bare": True}).text
        self.assertIn('"type": "error"', text)

    def test_normal_stream_not_marked_truncated(self):
        app = build_app(temp_db())
        app.state.chat_backend_for_test = StubChat("正常講完了。")
        text = TestClient(app).post(
            "/api/chat/stream", json={"history": [], "message": "問", "bare": True}).text
        self.assertIn('"truncated": ""', text)

    def test_distill_returns_candidates(self):
        app = build_app(temp_db())
        app.state.distill_factory = lambda hist: [
            SimpleNamespace(claim="根因X", kind="規律", ladder=["表面", "bedrock"],
                            evidence_urls=[], already=False)]
        r = TestClient(app).post("/api/chat/distill",
                                 json={"history": [{"role": "user", "content": "a"}]}).json()
        self.assertEqual(len(r["candidates"]), 1)
        self.assertEqual(r["candidates"][0]["claim"], "根因X")

    def test_anoint_human_gate_only_writes_bedrock(self):
        """純度守衛：distill 只候選、不寫地基；唯 anoint（人按）寫。"""
        db = temp_db()
        app = build_app(db)
        app.state.distill_factory = lambda hist: [
            SimpleNamespace(claim="候選根因", kind="", ladder=[], evidence_urls=[], already=False)]
        c = TestClient(app)
        c.post("/api/chat/distill", json={"history": [{"role": "user", "content": "a"}]})
        repo = Repository(db)
        self.assertEqual(repo.list_why_nodes("anointed"), [])   # distill 沒寫地基
        repo.close()
        r = c.post("/api/chat/anoint",
                   json={"claim": "室溫超導：BCS 電子配對", "ladder": "表面\nbedrock"}).json()
        self.assertEqual(r["status"], "created")
        repo = Repository(db)
        an = repo.list_why_nodes("anointed")
        self.assertEqual(len(an), 1)
        self.assertIn("BCS 電子配對", an[0].claim)
        repo.close()

    def test_anoint_idempotent(self):
        db = temp_db()
        c = TestClient(build_app(db))
        c.post("/api/chat/anoint", json={"claim": "同一條根因"})
        r2 = c.post("/api/chat/anoint", json={"claim": "同一條根因"}).json()
        self.assertEqual(r2["status"], "exists")               # 不重複收（原則 6 反囤積）
        repo = Repository(db)
        self.assertEqual(len(repo.list_why_nodes("anointed")), 1)
        repo.close()

    def test_roots_shape(self):
        db = temp_db()
        c = TestClient(build_app(db))
        c.post("/api/chat/anoint", json={"claim": "根因A", "evidence_urls": "https://a/1"})
        r = c.get("/api/roots").json()
        self.assertEqual(len(r["anointed"]), 1)
        for k in ("anointed", "candidates", "provenance", "source_provenance"):
            self.assertIn(k, r)

    def test_autosave_returns_temp_id(self):
        r = TestClient(build_app(temp_db())).post(
            "/api/chat/autosave",
            json={"history": [{"role": "user", "content": "hi"}], "temp_id": ""}).json()
        self.assertIn("temp_id", r)


@unittest.skipUnless(_DIST.is_dir(), "frontend 未 build（frontend/dist 不在）")
class TestSpaServed(unittest.TestCase):
    def test_app_serves_spa_index(self):
        """FastAPI 服務 React SPA 於根 /（含 client-route fallback）。"""
        c = TestClient(build_app(temp_db()))
        r = c.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn('id="root"', r.text)              # SPA 入口
        r2 = c.get("/roots")                             # 前端路由可直接開/重整→fallback index
        self.assertEqual(r2.status_code, 200)
        self.assertIn('id="root"', r2.text)

    def test_pwa_manifest_and_sw_served_not_html(self):
        """PWA：manifest/sw 是真檔（非 fallback 成 HTML），含 share_target。"""
        c = TestClient(build_app(temp_db()))
        m = c.get("/manifest.webmanifest")
        self.assertEqual(m.status_code, 200)
        self.assertIn("share_target", m.text)            # 手機分享目標
        self.assertEqual(c.get("/sw.js").status_code, 200)

    def test_api_route_not_shadowed_by_spa_mount(self):
        """SPA 掛在 / 當 catch-all，但實體路由（/api、匯出）先比對、不被吃掉。"""
        c = TestClient(build_app(temp_db()))
        self.assertEqual(c.get("/api/chat/state").status_code, 200)
        self.assertEqual(c.get("/conversations/999999/export").status_code, 404)  # 真路由（非 index.html）

    def test_share_target_ingests_and_redirects(self):
        """PWA Web Share Target：分享文字→收進→導回 /sources（Android）。"""
        db = temp_db()
        r = TestClient(build_app(db)).post(
            "/share-target",
            data={"text": "貓要吃貓糧與用貓砂很重要。" * 30, "title": "分享文"},
            follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("/sources", r.headers["location"])
        repo = Repository(db)
        self.assertGreaterEqual(len(repo.list_source_groups()), 1)   # 分享的收進了
        repo.close()


if __name__ == "__main__":
    unittest.main()
