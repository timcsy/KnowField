"""契約：整理台（spec 050）——清冊、批次搬、來源以 url 為身分。"""
import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

_M = [{"role": "user", "content": "嗨"}]
_URL = "https://example.com/paper"


def _seed(db):
    """一個來源（**兩塊**同 url）、一段對話、一條從那來源冊封的理解、一篇文章。"""
    repo = Repository(db)
    a = repo.create_domain("A"); b = repo.create_domain("B")
    d = repo.conn.execute(
        "INSERT INTO digests (date) VALUES ('2026-08-25') RETURNING id").fetchone()
    did = int(d["id"])
    eids = []
    for i in (1, 2):
        e = repo.conn.execute(
            "INSERT INTO digest_entries (digest_id, rank, title, url) VALUES (%s,%s,%s,%s)"
            " RETURNING id", (did, i, "某篇論文", _URL)).fetchone()
        eids.append(int(e["id"]))
    c = repo.autosave_temporary(None, _M, "2026-08-25T00:00:00Z")
    r = repo.conn.execute(
        "INSERT INTO why_nodes (claim, kind, status, conversation_id, source_entry_id)"
        " VALUES ('某條理解','推論','anointed',%s,%s) RETURNING id", (c, eids[0])).fetchone()
    w = int(r["id"])
    aid = repo.save_article("t", "標題", "內文", root_ids=[w])
    repo.conn.commit(); repo.close()
    return a, b, c, w, aid, eids


class TestOrganizerApi(unittest.TestCase):
    def test_inventory_lists_all_four_kinds(self):
        db = temp_db(); _seed(db)
        items = TestClient(build_app(db)).get("/api/knowledge/inventory").json()["items"]
        kinds = {i["kind"] for i in items}
        self.assertEqual(kinds, {"conversation", "why_node", "article", "source"})

    def test_a_source_is_one_row_per_url_not_per_chunk(self):
        """⚠️ 兩塊同 url ＝ **一個**來源。用 MIN(id) 當代表就會變成兩列。"""
        db = temp_db(); _seed(db)
        items = TestClient(build_app(db)).get("/api/knowledge/inventory").json()["items"]
        srcs = [i for i in items if i["kind"] == "source"]
        self.assertEqual([s["ref"] for s in srcs], [_URL])

    def test_moving_a_source_tags_every_chunk_of_that_url(self):
        db = temp_db(); a, b, c, w, aid, eids = _seed(db)
        TestClient(build_app(db)).post(
            "/api/knowledge/move",
            json={"items": [{"kind": "source", "ref": _URL}], "domain_id": a})
        repo = Repository(db)
        got = [repo.conn.execute("SELECT domain_id FROM digest_entries WHERE id=%s",
                                 (e,)).fetchone()["domain_id"] for e in eids]
        repo.close()
        self.assertEqual(got, [a, a], "⚠️ 只有第一塊帶到領域＝來源被切成兩半")

    def test_source_neighbours_include_its_anointed_roots(self):
        db = temp_db(); a, b, c, w, aid, eids = _seed(db)
        cl = TestClient(build_app(db))
        cl.post("/api/knowledge/move",
                json={"items": [{"kind": "why_node", "ref": w}], "domain_id": a})
        r = cl.post("/api/knowledge/tangles",
                    json={"items": [{"kind": "source", "ref": _URL}], "domain_id": b}).json()
        self.assertIn(("why_node", w), [(t["kind"], t["ref"]) for t in r["tangles"]])

    def test_batch_move_of_neighbours_reports_no_tangle(self):
        """⚠️ 一起搬的東西沒有被拆散——這是批次的全部意義。"""
        db = temp_db(); a, b, c, w, aid, eids = _seed(db)
        cl = TestClient(build_app(db))
        cl.post("/api/knowledge/move",
                json={"items": [{"kind": "conversation", "ref": c},
                                {"kind": "why_node", "ref": w}], "domain_id": a})
        r = cl.post("/api/knowledge/tangles",
                    json={"items": [{"kind": "conversation", "ref": c},
                                    {"kind": "why_node", "ref": w}], "domain_id": b}).json()
        self.assertEqual([t["ref"] for t in r["tangles"]], [], f"誤報：{r['tangles']}")

    def test_batch_move_moves_all(self):
        db = temp_db(); a, b, c, w, aid, eids = _seed(db)
        r = TestClient(build_app(db)).post(
            "/api/knowledge/move",
            json={"items": [{"kind": "conversation", "ref": c},
                            {"kind": "article", "ref": aid},
                            {"kind": "source", "ref": _URL}], "domain_id": b}).json()
        self.assertEqual(r["moved"], 3)
        repo = Repository(db)
        self.assertEqual(repo.knowledge_domain("conversation", c), b)
        self.assertEqual(repo.knowledge_domain("article", aid), b)
        self.assertEqual(repo.knowledge_domain("source", _URL), b)
        repo.close()


if __name__ == "__main__":
    unittest.main()
