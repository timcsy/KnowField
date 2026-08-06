"""web 測試共用：以暫存 DB＋離線後端建 app。"""

from __future__ import annotations

import os
import tempfile

from knowfield.models import Article, Digest, DigestEntry, Figure, Item
from knowfield.store.repository import Repository


def temp_db() -> str:
    return os.path.join(tempfile.mkdtemp(), "web.db")


def build_app(db_path: str):
    os.environ["KNOWFIELD_DB"] = db_path
    os.environ["KNOWFIELD_BACKEND"] = "offline"   # 明講離線（勝過 .env）
    from knowfield.web.app import create_app
    return create_app()


def seed_digest(db_path: str) -> None:
    """種一份含原文圖與 AI 圖的匯整供首頁測試。"""
    repo = Repository(db_path)
    e1 = DigestEntry(
        item=Item(source_id="s", external_id="1", title="Original Title",
                  url="https://a/1"),
        rank=1, relevance_score=0.9, matched_topic="agent",
        article=Article(item_id=0, body="第一段內容。\n\n第二段內容。",
                        source_url="https://a/1", headline="整理過的新聞標題",
                        figure=Figure(kind="原文", url="https://img/x.jpg",
                                      source_note="取自原文")))
    e2 = DigestEntry(
        item=Item(source_id="s", external_id="2", title="無圖標題", url="https://a/2"),
        rank=2, relevance_score=0.8, matched_topic="agent",
        article=Article(item_id=0, body="內容二。", source_url="https://a/2",
                        headline="第二則整理標題",
                        figure=Figure(kind="AI 示意", url="https://img/ai.png",
                                      source_note="AI 示意・非原文")))
    repo.save_digest(Digest(date="2026-07-23", entries=[e1, e2]))
    repo.close()
