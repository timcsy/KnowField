"""spec 068：一天三條複習。

⚠️ 這一刀最容易做壞的地方是**排序**：任何「熱門度」的訊號進到這裡，
就會變成馬太陷阱——被引用最多的一直被推到你眼前，
而你最需要重新遇到的正好是**你快忘了的那些**。
"""
import unittest
from datetime import datetime, timedelta, timezone

from knowfield.store.repository import Repository
from tests.web_helpers import temp_db

_NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Base(unittest.TestCase):
    def setUp(self):
        self.db = temp_db()
        self.r = Repository(self.db)
        self.ids = []
        for i in range(7):
            w = self.r.add_why_node(f"理解 {i}", [], [], False, 0, _NOW)
            self.r.anoint_why_node(w)
            self.ids.append(w)

    def tearDown(self):
        self.r.close()


class TestThreeADay(Base):
    def test_same_three_within_a_day(self):
        a = [x["id"] for x in self.r.rehearse(3)]
        b = [x["id"] for x in self.r.rehearse(3)]
        self.assertEqual(len(a), 3)
        self.assertEqual(a, b, "同一天又給了另外三條——那不是『一天三條』")

    def test_next_day_rotates(self):
        a = {x["id"] for x in self.r.rehearse(3)}
        # 把今天看過的往前推一天 ⇒ 模擬「隔天」
        y = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.r.conn.execute("UPDATE why_nodes SET last_rehearsed_at=%s WHERE last_rehearsed_at<>''", (y,))
        self.r.conn.commit()
        b = {x["id"] for x in self.r.rehearse(3)}
        self.assertEqual(len(a & b), 0, "隔天又推同樣三條——輪不到其他的")

    def test_eventually_covers_everything(self):
        """FR-003：**會輪完全部**——不會有永遠沒被看到的。"""
        seen = set()
        for _ in range(4):
            seen |= {x["id"] for x in self.r.rehearse(3)}
            y = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            self.r.conn.execute("UPDATE why_nodes SET last_rehearsed_at=%s"
                                " WHERE COALESCE(last_rehearsed_at,'')<>''", (y,))
            self.r.conn.commit()
        self.assertEqual(seen, set(self.ids))

    def test_fewer_than_three_does_not_crash(self):
        r = Repository(temp_db())
        w = r.add_why_node("只有一條", [], [], False, 0, _NOW)
        r.anoint_why_node(w)
        self.assertEqual(len(r.rehearse(3)), 1)
        r.close()


class TestNoMatthewEffect(Base):
    """⚠️ FR-004：本檔存在的主要理由。"""

    def test_popularity_does_not_win(self):
        """一條被大量引用的理解，不該因此被優先挑中。"""
        star = self.ids[-1]                       # 最後一條，時間上最不該先被挑
        aid = self.r.save_article("t", "一篇應用", "內文", "", "", _NOW, [star])
        for _ in range(5):                        # 讓它被引用很多次
            self.r.save_article("t", f"再一篇 {_}", "內文", "", "", _NOW, [star])
        self.assertTrue(aid)
        picked = [x["id"] for x in self.r.rehearse(3)]
        # 七條的 last_rehearsed_at 都是空的 ⇒ 挑選只能靠 id 順序，不能靠引用數
        self.assertNotIn(star, picked,
                         "被引用最多的被挑中了——熱門度餵進了排序（馬太陷阱）")


class TestBoundaries(Base):
    def test_archived_not_rehearsed(self):
        self.r.archive_knowledge("why_node", self.ids[0], _NOW)
        self.assertNotIn(self.ids[0], [x["id"] for x in self.r.rehearse(7)])

    def test_persona_isolated(self):
        rp = Repository(self.db, persona=999)
        got = [x["id"] for x in rp.rehearse(3)]
        rp.close()
        # 共用層看得到（persona_id IS NULL）⇒ 這裡驗的是**不會多看到別人的**
        self.assertTrue(set(got) <= set(self.ids))


if __name__ == "__main__":
    unittest.main()
