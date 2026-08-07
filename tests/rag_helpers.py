"""RAG 測試共用：暫存 DB＋種語料條目。"""

from __future__ import annotations

import contextlib
import io
import os
import tempfile

from knowfield.models import Article, Digest, DigestEntry, Item
from knowfield.store.repository import Repository


def temp_db() -> str:
    # spec 034：改回一個乾淨 PG 資料庫的 DSN（原為 SQLite 檔路徑）
    from tests.pgtest import fresh_pg_dsn
    return fresh_pg_dsn()


def make_entry(rank: int, title: str, url: str, headline: str, body: str,
               topic: str = "") -> DigestEntry:
    return DigestEntry(
        item=Item(source_id="s", external_id=str(rank), title=title, url=url),
        rank=rank, relevance_score=0.9, matched_topic=topic,
        article=Article(item_id=0, body=body, source_url=url, headline=headline),
    )


def seed_digest(repo: Repository, date: str, entries: list[DigestEntry]) -> None:
    repo.save_digest(Digest(date=date, entries=entries))


def capture(fn, *args) -> tuple[int, str]:
    """跑 fn(*args)、擷取 stdout，回 (退出碼, 輸出)。"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*args)
    return rc, buf.getvalue()
