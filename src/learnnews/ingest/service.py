"""ContentIngestService（spec 030）：把貼上文字/PDF 切塊、存成 corpus 條目。

核心洞見：一段內容切成多塊、每塊當一筆 digest_entry 存 → `retrieve_corpus`（spec 029）／`/chat`
自動吃到、自動標「你收藏的」、自動不進地基（只讀 anointed why_nodes）。無新表（教訓 8）。
轉檔器可注入（教訓 1 離線可測）；轉檔/切塊失敗不寫半殘（教訓 3）。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from ..models import Article, Item
from ..rag.service import embedder_tag
from ..rag.types import CorpusEntry
from ..sources.base import SourceUnavailable
from .chunk import chunk_markdown


@dataclass
class ContentIngestResult:
    status: str            # 'ingested' | 'empty' | 'exists'
    title: str = ""
    count: int = 0


def _first_line_title(text: str) -> str:
    for line in (text or "").splitlines():
        t = line.strip().lstrip("#").strip()
        if t:
            return t[:40]
    return "貼上的內容"


def store_chunks(repo, embedder, title: str, url: str, chunks: list[str],
                 source_class: str = "ordinary") -> int:
    """逐塊存成 digest_entry（一來源→多筆）＋批次 embed。回塊數。"""
    ces: list[CorpusEntry] = []
    n = len(chunks)
    for i, ch in enumerate(chunks, 1):
        headline = f"{title}（{i}/{n}）" if n > 1 else title
        item = Item(source_id="content", external_id=f"{url}#{i}", title=title, url=url)
        article = Article(item_id=0, body=ch, source_url=url, headline=headline)
        eid = repo.ingest_seed(item, article, source_class)
        ces.append(CorpusEntry(entry_id=eid, title=title, url=url, headline=headline,
                               body=ch, source_class=source_class))
    if ces:
        repo.ensure_embeddings(ces, embedder, embedder_tag(embedder))
    return n


class ContentIngestService:
    def __init__(self, repo, embedder, converter=None) -> None:
        self.repo = repo
        self.embedder = embedder
        self.converter = converter        # DocConverter（PDF→markdown）；貼上不需要

    def _ingest_markdown(self, md: str, title: str, url: str) -> ContentIngestResult:
        if self.repo.seed_exists(url) is not None:        # 同來源已收→不重複增生
            return ContentIngestResult(status="exists", title=title)
        chunks = chunk_markdown(md or "")
        if not chunks:
            return ContentIngestResult(status="empty")
        n = store_chunks(self.repo, self.embedder, title, url, chunks)
        return ContentIngestResult(status="ingested", title=title, count=n)

    def ingest_text(self, text: str, title: str = "") -> ContentIngestResult:
        text = text or ""
        if not text.strip():
            return ContentIngestResult(status="empty")
        title = (title or "").strip() or _first_line_title(text)
        url = f"paste:{hashlib.sha1(text.encode('utf-8')).hexdigest()[:16]}"
        return self._ingest_markdown(text, title, url)

    def ingest_url(self, url: str, title: str = "", http_get=None) -> ContentIngestResult:
        """收整篇網頁（開放文章/Blog）：抓 HTML→抽正文 markdown→切塊→存。best-effort。"""
        from ..seed.fetch import default_http_get
        from .web import extract_article_markdown
        url = (url or "").strip()
        if not url:
            return ContentIngestResult(status="empty")
        html = (http_get or default_http_get)(url)          # 抓不到→SourceUnavailable（邊界攔）
        extracted_title, md = extract_article_markdown(html)
        if not (md or "").strip():
            return ContentIngestResult(status="empty")
        title = (title or "").strip() or extracted_title or url
        return self._ingest_markdown(md, title, url)

    def ingest_pdf(self, pdf_bytes: bytes | None = None, pdf_url: str = "",
                   title: str = "") -> ContentIngestResult:
        if self.converter is None:
            raise SourceUnavailable("未設定 PDF 轉檔器")
        md = self.converter.to_markdown(pdf_bytes=pdf_bytes, pdf_url=pdf_url or None)
        if not (md or "").strip():
            return ContentIngestResult(status="empty")
        title = (title or "").strip() or (pdf_url or "PDF 文件")
        url = pdf_url or f"pdf:{hashlib.sha1((title or 'pdf').encode('utf-8')).hexdigest()[:16]}"
        return self._ingest_markdown(md, title, url)
