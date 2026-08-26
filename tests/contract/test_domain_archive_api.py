"""契約：封存（spec 055）——離開活的場，留下遺骸。"""
import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

_M = [{"role": "user", "content": "嗨"}]


def _seed(db):
    repo = Repository(db)
    ai = repo.create_domain("AI")
    gen = repo.create_domain("生成模型", ai)
    flow = repo.create_domain("Flow Matching", gen)
    c = repo.autosave_temporary(None, _M, "2026-08-26T00:00:00Z", domain_id=gen)
    r = repo.conn.execute(
        "INSERT INTO why_nodes (claim, kind, status, domain_id)"
        " VALUES ('理解','推論','anointed',%s) RETURNING id", (flow,)).fetchone()
    w = int(r["id"]); repo.conn.commit(); repo.close()
    return ai, gen, flow, c, w


class TestArchiveApi(unittest.TestCase):
    def test_preview_reports_the_subtree_and_changes_nothing(self):
        db = temp_db(); ai, gen, flow, c, w = _seed(db)
        cl = TestClient(build_app(db))
        r = cl.get(f"/api/domains/{gen}/archive-preview").json()
        self.assertEqual((r["items"], r["children"], r["to"]), (2, 1, ai))
        repo = Repository(db)
        self.assertIn(gen, [d["id"] for d in repo.list_domains()])
        repo.close()

    def test_archive_takes_the_subtree_and_leaves_remnants(self):
        db = temp_db(); ai, gen, flow, c, w = _seed(db)
        cl = TestClient(build_app(db))
        cl.post(f"/api/domains/{gen}/archive")
        repo = Repository(db)
        self.assertEqual([d["id"] for d in repo.list_domains()], [ai], "子領域沒跟著封存")
        self.assertEqual(repo._inventory_rows(), [], "底下的知識沒跟著封存")
        self.assertIn(gen, [d["id"] for d in repo.archived_domains()], "沒留下遺骸")
        repo.close()

    def test_restore_brings_the_batch_back(self):
        db = temp_db(); ai, gen, flow, c, w = _seed(db)
        cl = TestClient(build_app(db))
        cl.post(f"/api/domains/{gen}/archive")
        cl.post(f"/api/domains/{gen}/restore")
        repo = Repository(db)
        self.assertEqual({d["id"] for d in repo.list_domains()}, {ai, gen, flow})
        self.assertEqual(len(repo._inventory_rows()), 2)
        repo.close()

    def test_archiving_a_single_piece_of_knowledge(self):
        db = temp_db(); ai, gen, flow, c, w = _seed(db)
        cl = TestClient(build_app(db))
        r = cl.post("/api/knowledge/archive",
                    json={"items": [{"kind": "why_node", "ref": w}]}).json()
        self.assertTrue(r["ok"])
        repo = Repository(db)
        self.assertEqual([x.id for x in repo.list_why_nodes("anointed")], [])
        self.assertIn(("why_node", w), [(x["kind"], x["ref"]) for x in repo.archived_items()])
        repo.close()

    def test_archived_list_is_queryable(self):
        db = temp_db(); ai, gen, flow, c, w = _seed(db)
        cl = TestClient(build_app(db))
        cl.post("/api/knowledge/archive", json={"items": [{"kind": "why_node", "ref": w}]})
        r = cl.get("/api/archived").json()
        self.assertEqual([x["ref"] for x in r["items"]], [w])
        self.assertEqual(r["domains"], [])


if __name__ == "__main__":
    unittest.main()
