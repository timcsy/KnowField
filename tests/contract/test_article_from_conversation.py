"""契約：從對話生文章（spec 043）。離線注入、零外呼。"""
import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db


class _Cap:
    def __init__(self): self.prompt = ""
    def reply(self, messages):
        self.prompt = "\n".join(m["content"] for m in messages)
        return "## 標題\n\n內容。"
    def stream(self, messages):
        yield ""


class _Emb:
    def embed(self, t): return [1.0, 0.0]
    def embed_many(self, ts): return [[1.0, 0.0] for _ in ts]


def _seed(db, n_field=10, refs=(("推論", "對話的第一條"), ("類比", "對話的第二條"))):
    """種一個場 ＋ 一段對話，並把 refs 綁成該對話的由來。"""
    from knowfield.models import Item
    repo = Repository(db)
    for i in range(n_field):
        repo.add_why_node_raw(f"場裡第 {i} 條", "推論") if hasattr(repo, "add_why_node_raw") else None
    cid = repo.save_conversation("測試對話", [{"role": "user", "content": "嗨"}])
    ids = []
    for kind, claim in refs:
        r = repo.conn.execute(
            "INSERT INTO why_nodes (claim, kind, status, conversation_id) VALUES (%s,%s,'anointed',%s)"
            " RETURNING id", (claim, kind, cid)).fetchone()
        ids.append(int(r["id"]))
    for i in range(n_field):
        repo.conn.execute(
            "INSERT INTO why_nodes (claim, kind, status) VALUES (%s,'推論','anointed')",
            (f"場裡第 {i} 條",))
    repo.conn.commit()
    repo.close()
    return cid, ids


def _app(db):
    app = build_app(db)
    cap = _Cap()
    app.state.chat_backend_for_test = cap
    app.state.embedder_for_test = _Emb()
    return app, cap


class TestArticleFromConversation(unittest.TestCase):
    def test_referrers_reach_the_model(self):
        """FR-002／SC-001：那段對話冊封出的東西一定被納入。"""
        db = temp_db(); cid, _ = _seed(db)
        app, cap = _app(db)
        r = TestClient(app).post("/api/article", json={"conversation_id": cid})
        self.assertEqual(r.status_code, 200)
        seen = cap.prompt + "\n" + (r.json().get("markdown") or "")
        self.assertIn("對話的第一條", seen)
        self.assertIn("對話的第二條", seen)

    def test_analogy_referrer_not_in_body(self):
        """FR-003／SC-003：類比不得因為釘住而進正文。"""
        db = temp_db(); cid, _ = _seed(db)
        app, cap = _app(db)
        TestClient(app).post("/api/article", json={"conversation_id": cid})
        self.assertNotIn("對話的第二條", cap.prompt, "類比被釘進正文的 prompt")

    def test_empty_referrers_gives_an_actionable_message(self):
        """FR-006：死路要變成下一步，不是空白也不是 5xx。"""
        db = temp_db()
        repo = Repository(db)
        cid = repo.save_conversation("沒冊封過的對話", [{"role": "user", "content": "嗨"}])
        repo.conn.execute("INSERT INTO why_nodes (claim, kind, status) VALUES ('場的一條','推論','anointed')")
        repo.conn.commit(); repo.close()
        app, _ = _app(db)
        r = TestClient(app).post("/api/article", json={"conversation_id": cid})
        self.assertEqual(r.status_code, 200)
        self.assertIn("精選", r.json().get("error") or "")

    def test_missing_conversation_is_explicit(self):
        db = temp_db(); _seed(db)
        app, _ = _app(db)
        r = TestClient(app).post("/api/article", json={"conversation_id": 99999})
        self.assertTrue((r.json().get("error") or ""), "對話不存在卻沒說")

    def test_topic_path_unchanged(self):
        """⚠️ FR-007／SC-005：不帶 conversation_id 時與現況逐字相同。
        比對的是寫死的預期（沒有 pinned 痕跡、topic 原樣回傳），不是拿自己比自己。"""
        db = temp_db(); _seed(db)
        app, cap = _app(db)
        r = TestClient(app).post("/api/article", json={"topic": "自己打的主題"})
        self.assertEqual(r.json().get("title"), "自己打的主題")
        self.assertNotIn("對話的第一條", cap.prompt)

    def test_storage_unchanged(self):
        """FR-008。"""
        db = temp_db(); cid, _ = _seed(db)
        repo = Repository(db)
        before = [(w.id, w.claim, w.status) for w in repo.list_why_nodes("anointed")]
        n_before = len(repo.list_articles()); repo.close()
        app, _ = _app(db)
        TestClient(app).post("/api/article", json={"conversation_id": cid})
        repo = Repository(db)
        after = [(w.id, w.claim, w.status) for w in repo.list_why_nodes("anointed")]
        self.assertEqual(before, after)
        self.assertEqual(n_before, len(repo.list_articles()), "生成不該自動存檔（人閘門）")
        repo.close()
