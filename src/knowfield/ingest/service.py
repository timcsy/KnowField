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


def _first_heading(md: str) -> str:
    """內容裡第一個 markdown 標題（# …）＝文章自己的標題，最貼近原標題。無→""。"""
    for line in (md or "").splitlines():
        s = line.strip()
        if s.startswith("#"):
            return s.lstrip("#").strip()[:80]
    return ""


_TITLE = ("以下是一篇文章的內容。請給出**這篇文章的標題**——內容裡本來就有標題就用它、盡量**貼近原標題**，"
          "**不要自己摘要或改寫**。不超過 30 字，只輸出標題本身，不要引號或前綴。")


def _gen_title(text: str, backend) -> str:
    """沒給標題時請 LLM 生一個。backend 為 None／失敗→""（退回首行，教訓 3）。"""
    if backend is None or not (text or "").strip():
        return ""
    try:
        out = backend.reply([{"role": "system", "content": _TITLE},
                             {"role": "user", "content": text[:1500]}])
    except Exception:  # noqa: BLE001 - 生標題失敗不擋收進
        return ""
    t = (out or "").strip().splitlines()[0].strip().strip('"「」 ') if out else ""
    return t[:40]


def store_chunks(repo, embedder, title: str, url: str, chunks: list[str],
                 source_class: str = "ordinary", note: str = "", ingested_at: str = "") -> int:
    """逐塊存成 digest_entry（一來源→多筆）＋批次 embed。note/ingested_at＝收進原因/日期。回塊數。"""
    ces: list[CorpusEntry] = []
    n = len(chunks)
    for i, ch in enumerate(chunks, 1):
        headline = f"{title}（{i}/{n}）" if n > 1 else title
        item = Item(source_id="content", external_id=f"{url}#{i}", title=title, url=url)
        article = Article(item_id=0, body=ch, source_url=url, headline=headline)
        eid = repo.ingest_seed(item, article, source_class, note=note, ingested_at=ingested_at)
        ces.append(CorpusEntry(entry_id=eid, title=title, url=url, headline=headline,
                               body=ch, source_class=source_class))
    if ces:
        repo.ensure_embeddings(ces, embedder, embedder_tag(embedder))
    return n


class ContentIngestService:
    def __init__(self, repo, embedder, converter=None, chat_backend=None,
                 media_dir: str = "") -> None:
        self.repo = repo
        self.embedder = embedder
        self.converter = converter        # DocConverter（PDF→markdown）；貼上不需要
        self.chat_backend = chat_backend  # 選用 LLM 清理（spec 031 US4）
        self.media_dir = media_dir        # 非空＝下載外連圖到本地（否則圖維持外連 URL）

    def _resolve_title(self, given: str, text: str, extracted: str = "") -> str:
        """標題優先序：人給 > 文章原標題（h1/<title>）> 內文第一個標題 > AI 忠實抽 > 首行。"""
        return ((given or "").strip()
                or (extracted or "").strip()      # extract 已優先文章 h1（真標題），退回 <title>
                or _first_heading(text)
                or _gen_title(text, self.chat_backend)
                or _first_line_title(text))

    def _ingest_markdown(self, md: str, title: str, url: str,
                         note: str = "", ingested_at: str = "") -> ContentIngestResult:
        if self.repo.seed_exists(url) is not None:        # 同來源已收→不重複增生
            return ContentIngestResult(status="exists", title=title)
        if self.media_dir:                                # 外連圖→下載在地化（抓不到保留外連）
            from .media import localize_images
            md, _ = localize_images(md or "", self.media_dir)
        chunks = chunk_markdown(md or "")
        if not chunks:
            return ContentIngestResult(status="empty")
        n = store_chunks(self.repo, self.embedder, title, url, chunks,
                         note=(note or "").strip(), ingested_at=(ingested_at or "").strip())
        return ContentIngestResult(status="ingested", title=title, count=n)

    def ingest_text(self, text: str, title: str = "", html: str = "",
                    clean: bool = False, source_url: str = "",
                    note: str = "", ingested_at: str = "") -> ContentIngestResult:
        """貼上收進。html 非空＝rich-paste：抽正文 markdown（含圖片、剝 boilerplate）；否則純文字。
        clean=True＝LLM 深度清理（選用）。source_url＝原網址（可選，當來源 url／回出處／去重）。"""
        etitle = ""
        if (html or "").strip():
            from .web import extract_article_markdown
            etitle, md = extract_article_markdown(html, base_url=(source_url or "").strip())
            if md.strip():
                text = md
        text = text or ""
        if not text.strip():
            return ContentIngestResult(status="empty")
        if clean:
            from .clean import clean_markdown
            text = clean_markdown(text, self.chat_backend)
        title = self._resolve_title(title, text, etitle)     # 沒標題→AI 生（失敗退回首行）
        url = (source_url or "").strip() or f"paste:{hashlib.sha1(text.encode('utf-8')).hexdigest()[:16]}"
        return self._ingest_markdown(text, title, url, note=note, ingested_at=ingested_at)

    def ingest_url(self, url: str, title: str = "", http_get=None,
                   note: str = "", ingested_at: str = "") -> ContentIngestResult:
        """收整篇網頁（開放文章/Blog）：抓 HTML→抽正文 markdown→切塊→存。best-effort。"""
        from ..seed.fetch import default_http_get
        from .web import extract_article_markdown, normalize_ingest_url
        url = (url or "").strip()
        if not url:
            return ContentIngestResult(status="empty")
        fetch_url, store_url = normalize_ingest_url(url)     # arxiv abs/pdf→抓 HTML 版、存回 /abs
        html = (http_get or default_http_get)(fetch_url)    # 抓不到→SourceUnavailable（邊界攔）
        extracted_title, md = extract_article_markdown(html, base_url=fetch_url)
        if not (md or "").strip():
            return ContentIngestResult(status="empty")
        title = self._resolve_title(title, md, extracted_title)
        return self._ingest_markdown(md, title, store_url, note=note, ingested_at=ingested_at)

    def ingest_youtube(self, url: str, title: str = "", http_get=None) -> ContentIngestResult:
        """收 YouTube 逐字稿：抓字幕→切塊→存。抓不到字幕→SourceUnavailable（改用貼上）。"""
        from ..seed.fetch import default_http_get
        from .youtube import fetch_transcript
        vtitle, transcript = fetch_transcript((url or "").strip(), http_get or default_http_get)
        if not transcript.strip():
            return ContentIngestResult(status="empty")
        title = (title or "").strip() or vtitle or url
        return self._ingest_markdown(transcript, title, (url or "").strip())

    def ingest_pdf(self, pdf_bytes: bytes | None = None, pdf_url: str = "",
                   title: str = "", note: str = "", ingested_at: str = "") -> ContentIngestResult:
        if self.converter is None:
            raise SourceUnavailable("未設定 PDF 轉檔器")
        md = self.converter.to_markdown(pdf_bytes=pdf_bytes, pdf_url=pdf_url or None)
        if not (md or "").strip():
            return ContentIngestResult(status="empty")
        title = self._resolve_title(title, md, "")       # PDF 沒標題→AI 生（勝過用檔名/URL）
        url = pdf_url or f"pdf:{hashlib.sha1((title or 'pdf').encode('utf-8')).hexdigest()[:16]}"
        return self._ingest_markdown(md, title, url, note=note, ingested_at=ingested_at)
