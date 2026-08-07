"""可攜資料層 adapter（spec 036，vision 階段 33）：一份資料層碼跑 SQLite（本地零 server）或 Postgres（prod）。

薄包裝，非 ORM：資料層 SQL 一律寫 `%s` 佔位符＋RETURNING＋ON CONFLICT（現代 SQLite ≥3.35 皆支援）；
sqlite 後端在 execute 時把 `%s`→`?`。row 皆支援 r["c"]／r.keys()／dict(r)（psycopg dict_row 與 sqlite3.Row 相容）。
後端由連線字串判斷：postgres(ql)://→PG；其餘（檔案路徑／:memory:／sqlite://）→SQLite。
"""

from __future__ import annotations


class _Conn:
    """統一 sqlite3 / psycopg 連線的薄包裝。"""

    def __init__(self, raw, dialect: str) -> None:
        self._raw = raw
        self.dialect = dialect          # "sqlite" | "postgres"

    def execute(self, sql: str, params=None):
        if self.dialect == "sqlite":
            sql = sql.replace("%s", "?")   # 資料層一律寫 %s；SQLite 用 ?（SQL 無字面 % 故安全）
        return self._raw.execute(sql, params if params is not None else ())

    def commit(self) -> None:
        self._raw.commit()

    def close(self) -> None:
        self._raw.close()


def _is_postgres(url: str) -> bool:
    return url.startswith(("postgres://", "postgresql://"))


def connect(url: str) -> _Conn:
    """依連線字串選後端。postgres(ql)://→PG；其餘→SQLite（檔案/:memory:/sqlite://…）。"""
    if _is_postgres(url):
        import psycopg
        from psycopg.rows import dict_row
        return _Conn(psycopg.connect(url, row_factory=dict_row), "postgres")
    import sqlite3
    path = url
    if url.startswith("sqlite://"):        # sqlite:///rel 或 sqlite:////abs → 取路徑
        path = url[len("sqlite://"):]
        path = path.lstrip("/") or ":memory:"
        if url.startswith("sqlite:////"):  # 四斜線＝絕對路徑
            path = "/" + path
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return _Conn(conn, "sqlite")
