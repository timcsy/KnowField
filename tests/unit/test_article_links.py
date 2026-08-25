"""spec 049 前置：文章的連結落庫。

⚠️ 為什麼要做：`articles` 的連結欄現在是**空的**——References 是生成時算出來
寫進 markdown **字串**的，那是文字不是連結。
⇒ 搬文章時系統不知道它跟什麼糾纏，而那**不會顯示成「沒關係」，會顯示成「沒問題」**。
"""
import unittest

from knowfield.output.article import generate_article
from knowfield.store.repository import Repository
from tests.rag_helpers import temp_db


class _Node:
    def __init__(self, i, claim, kind="推論"):
        self.id, self.claim, self.kind = i, claim, kind
        self.status, self.evidence, self.source_url = "anointed", "", ""


class _Backend:
    def reply(self, m): return "## 標題\n\n內容。"


class TestGenerateReportsUsedNodes(unittest.TestCase):
    """⚠️ 生成端要**講出**用了哪些節點——不能讓落庫端自己再算一次。
    再算一次就會與實際寫進文章的那批漂開，而漂開不會報錯。"""

    def test_returns_used_ids_split_by_layer(self):
        body = [_Node(i, f"正文 {i}", "推論") for i in range(1, 4)]
        ext = [_Node(9, "延伸的", "類比")]
        out = generate_article("主題", body + ext, _Backend(), embedder=None)
        self.assertEqual(set(out["used_body_ids"]), {1, 2, 3})
        self.assertEqual(set(out["used_ext_ids"]), {9})

    def test_empty_when_no_material(self):
        out = generate_article("主題", [_Node(9, "只有類比", "類比")], _Backend(), embedder=None)
        self.assertTrue(out["empty"])
        self.assertEqual(out.get("used_body_ids"), [])


class TestArticleLinksStored(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(temp_db())

    def tearDown(self):
        self.repo.close()

    def _roots(self, n=3):
        ids = []
        for i in range(n):
            r = self.repo.conn.execute(
                "INSERT INTO why_nodes (claim, kind, status) VALUES (%s,'推論','anointed')"
                " RETURNING id", (f"理解{i}",)).fetchone()
            ids.append(int(r["id"]))
        self.repo.conn.commit()
        return ids

    def test_save_records_roots_and_conversation(self):
        ids = self._roots()
        cid = self.repo.autosave_temporary(None, [{"role": "user", "content": "嗨"}],
                                           "2026-08-25T00:00:00Z")
        aid = self.repo.save_article("主題", "標題", "內文", root_ids=ids, conversation_id=cid)
        self.assertEqual(sorted(self.repo.article_roots(aid)), sorted(ids))
        self.assertEqual(self.repo.get_article(aid)["conversation_id"], cid)

    def test_no_links_is_empty_not_error(self):
        aid = self.repo.save_article("主題", "標題", "內文")
        self.assertEqual(self.repo.article_roots(aid), [])
        self.assertIsNone(self.repo.get_article(aid)["conversation_id"])

    def test_existing_signature_still_works(self):
        """⚠️ 既有呼叫端（只傳前幾個位置參數）不能壞。"""
        aid = self.repo.save_article("主題", "標題", "內文", "short", "intro", "2026-08-25")
        self.assertEqual(self.repo.get_article(aid)["length"], "short")
