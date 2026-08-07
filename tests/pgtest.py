"""spec 034：整合測試的 Postgres 供給。

session 級 testcontainer PG（lazy 起、atexit 停），每次 fresh_pg_dsn() 建一個乾淨資料庫回其 DSN
＝per-test 隔離（等價原 SQLite :memory:／temp file）。**核心測試不呼叫這裡 → 不需 PG**（守零安裝離線）。
"""

from __future__ import annotations

import atexit
import itertools
import re
import threading
from urllib.parse import urlparse

import psycopg

_lock = threading.Lock()
_state: dict = {"admin": None}
_counter = itertools.count()


def _admin_dsn() -> str:
    """起（或取）共享 PG 容器，回連到預設 db 的 admin DSN。"""
    with _lock:
        if _state["admin"] is None:
            from testcontainers.postgres import PostgresContainer
            c = PostgresContainer("postgres:15-alpine")
            c.start()
            atexit.register(c.stop)
            _state["admin"] = re.sub(r"\+\w+://", "://", c.get_connection_url())
        return _state["admin"]


def fresh_pg_dsn() -> str:
    """在共享容器上建一個乾淨資料庫，回其 DSN（per-test 隔離）。"""
    admin = _admin_dsn()
    p = urlparse(admin)
    dbname = f"kf_test_{next(_counter)}"
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{dbname}"')
    return f"postgresql://{p.username}:{p.password}@{p.hostname}:{p.port}/{dbname}"
