"""spec 044：對**既有**表冪等補欄。專案第一次做這件事。

⚠️ 為什麼不能用 try/except 硬加：那會把「欄已存在」跟「型別寫錯／表不存在／權限不足」
混成同一件事——真的錯了也靜默過去。這兩天連續撞到的就是這類（history/102、104）。
"""
import os
import sqlite3
import tempfile
import unittest

from knowfield.store import db, schema


def _legacy_db() -> str:
    """造一個「舊」資料庫：conversations 缺新欄、而且**有資料**。"""
    path = os.path.join(tempfile.mkdtemp(), "legacy.db")
    c = sqlite3.connect(path)
    c.execute("""CREATE TABLE conversations (
        id INTEGER PRIMARY KEY, title TEXT, messages TEXT DEFAULT '[]',
        why_node_id INTEGER, created_at TEXT, temporary INTEGER DEFAULT 0,
        last_activity_at TEXT, chapters TEXT DEFAULT '[]')""")
    c.execute("INSERT INTO conversations (title, messages, created_at)"
              " VALUES ('舊對話','[{\"role\":\"user\",\"content\":\"嗨\"}]','2026-01-01')")
    c.commit(); c.close()
    return path


def _cols(conn, table):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


class TestEnsureColumns(unittest.TestCase):
    def test_adds_missing_columns_without_touching_rows(self):
        """SC-001：欄補上、資料一列都沒動。"""
        path = _legacy_db()
        conn = db.connect(path)
        before = [dict(r) for r in conn.execute("SELECT * FROM conversations").fetchall()]
        schema.init_db(conn)
        cols = _cols(conn, "conversations")
        self.assertIn("carried_kind", cols)
        self.assertIn("carried_ref", cols)
        after = conn.execute("SELECT id, title, messages, created_at FROM conversations").fetchall()
        self.assertEqual(len(after), len(before))
        self.assertEqual(after[0]["title"], "舊對話")
        self.assertEqual(after[0]["messages"], before[0]["messages"])
        conn.close()

    def test_idempotent(self):
        """SC-002：連跑三次不報錯、欄不重複。"""
        path = _legacy_db()
        conn = db.connect(path)
        for _ in range(3):
            schema.init_db(conn)
        n = [r["name"] for r in conn.execute("PRAGMA table_info(conversations)").fetchall()]
        self.assertEqual(n.count("carried_kind"), 1)
        conn.close()

    def test_missing_table_is_not_swallowed(self):
        """⚠️ FR-003：表不存在時要**丟出來**。

        這條是本檔的核心：它擋的不是「加欄失敗」，是**加欄失敗被當成沒事**。
        try/except 版本會讓型別寫錯、權限不足這些真錯誤全部靜默。
        """
        conn = db.connect(os.path.join(tempfile.mkdtemp(), "empty.db"))
        with self.assertRaises(Exception):
            schema._ensure_columns(conn, [("no_such_table", "x", "TEXT")])
        conn.close()
