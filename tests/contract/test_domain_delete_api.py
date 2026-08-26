"""契約：刪領域（spec 054）——刪的是位置，不是知識。"""
import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

_M = [{"role": "user", "content": "嗨"}]


def _seed(db):
    repo = Repository(db)
    ai = repo.create_domain("AI")
    gen = repo.create_domain("生成模型", ai)
    repo.create_domain("Flow Matching", gen)
    c = repo.autosave_temporary(None, _M, "2026-08-26T00:00:00Z", domain_id=gen)
    repo.close()
    return ai, gen, c


class TestDeleteDomainApi(unittest.TestCase):
    def test_preview_reports_and_changes_nothing(self):
        db = temp_db(); ai, gen, c = _seed(db)
        cl = TestClient(build_app(db))
        r = cl.get(f"/api/domains/{gen}/delete-preview").json()
        self.assertEqual((r["items"], r["children"], r["to"]), (1, 1, ai))
        repo = Repository(db)
        self.assertIn(gen, [d["id"] for d in repo.list_domains()])
        repo.close()

    def test_delete_keeps_every_piece_of_knowledge(self):
        db = temp_db(); ai, gen, c = _seed(db)
        repo = Repository(db); before = len(repo._inventory_rows()); repo.close()
        TestClient(build_app(db)).post(f"/api/domains/{gen}/delete")
        repo = Repository(db)
        self.assertEqual(len(repo._inventory_rows()), before, "⚠️ 刪領域把知識刪掉了")
        self.assertEqual(repo.knowledge_domain("conversation", c), ai)
        self.assertIn("Flow Matching", [d["name"] for d in repo.list_domains()])
        repo.close()


if __name__ == "__main__":
    unittest.main()
