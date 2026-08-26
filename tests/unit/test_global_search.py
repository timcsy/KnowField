"""spec 066：全域搜尋。

⚠️ 搜尋是**最容易漏掉硬邊界**的地方——它天生的動作就是「把全部撈出來」。
所以這裡最重要的兩支測試不是「搜得到」，是**「搜不到不該搜到的」**。
"""
import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from knowfield.models import Article, Digest, DigestEntry, Item
from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

_NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Base(unittest.TestCase):
    def setUp(self):
        self.db = temp_db()
        self.app = build_app(self.db)
        self.c = TestClient(self.app)
        r = Repository(self.db)
        # 標題裡沒有「渦流」，只有內容裡有 ⇒ 驗 FR-002
        self.cid = r.save_conversation("一段普通的互動",
                                       [{"role": "user", "content": "談談渦流的形成"}], None)
        self.wid = r.add_why_node("流體在邊界層分離時會產生渦流", [], [], False, 0, _NOW)
        r.anoint_why_node(self.wid)
        r.save_digest(Digest(date="2026-08-26", entries=[DigestEntry(
            item=Item(source_id="s", external_id="1", title="邊界層筆記",
                      url="https://example.com/bl"),
            rank=1, relevance_score=0.9, matched_topic="t",
            article=Article(item_id=0, body="內文提到渦流脫落", source_url="https://example.com/bl",
                            headline="邊界層筆記"))]))
        self.aid = r.save_article("流體", "流體入門", "本文談渦流", "medium", "intro", _NOW, [self.wid])
        r.close()

    def find(self, q):
        return self.c.get("/api/search", params={"q": q}).json()


class TestFindsThings(Base):
    def test_matches_content_not_just_title(self):
        """FR-002：只比標題＝只找得到你已經記得名字的東西。"""
        g = self.find("渦流")
        kinds = {x["kind"] for grp in g["groups"] for x in grp["items"]}
        self.assertIn("why_node", kinds)
        self.assertIn("conversation", kinds, "互動的**內容**沒被搜到")
        self.assertIn("source", kinds, "來源的**內文**沒被搜到")
        self.assertIn("article", kinds)

    def test_grouped_with_counts(self):
        g = self.find("渦流")
        for grp in g["groups"]:
            self.assertEqual(grp["count"], len(grp["items"]))
            self.assertIn(grp["kind"], ("source", "conversation", "why_node", "article"))

    def test_blank_query_does_not_hit_the_db(self):
        for q in ("", "   "):
            self.assertEqual(self.find(q)["groups"], [])


class TestHardBoundaries(Base):
    """⚠️ 本檔存在的主要理由。"""

    def test_archived_is_not_searchable(self):
        r = Repository(self.db)
        r.archive_knowledge("why_node", self.wid, _NOW)
        r.close()
        refs = [(x["kind"], x["ref"]) for grp in self.find("渦流")["groups"] for x in grp["items"]]
        self.assertNotIn(("why_node", self.wid), refs,
                         "封存過的還搜得到——遺骸不該回到活的場（spec 064 同一條）")

    def test_other_owners_are_invisible(self):
        """⚠️ 換一個 owner 的 repo 去搜，一件都不該有。"""
        r2 = Repository(self.db, owner=2)
        self.assertEqual(r2.search("渦流"), [])
        r2.close()
        r1 = Repository(self.db, owner=1)
        self.assertTrue(r1.search("渦流"))
        r1.close()


if __name__ == "__main__":
    unittest.main()
