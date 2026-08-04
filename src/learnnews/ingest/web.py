"""網頁正文→markdown 抽取（spec 030 增量：URL 抓正文那張嘴）。

stdlib HTMLParser、零相依、離線可測。抽 <title> ＋標題(h1-6)/段落(p)/清單(li)/引言(blockquote)
成 markdown，略過 nav/script/style/footer 等 boilerplate。品質為便宜的 readability 級——
存取難/結構要求高的走「貼上」；這條是開放網頁的**便利**嘴（best-effort）。抓下來的 markdown
再走同一條 `chunk_markdown → store_chunks`。
"""

from __future__ import annotations

from html.parser import HTMLParser

_SKIP = {"script", "style", "nav", "header", "footer", "aside",
         "form", "button", "svg", "noscript", "figure"}
_HEAD = {"h1", "h2", "h3", "h4", "h5", "h6"}
_BLOCK = _HEAD | {"p", "li", "blockquote"}


class _ArticleMarkdown(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.blocks: list[str] = []
        self._in_title = False
        self._skip = 0
        self._mode: str | None = None
        self._cur: list[str] = []

    def _flush(self):
        text = " ".join("".join(self._cur).split())
        self._cur = []
        mode, self._mode = self._mode, None
        if not text:
            return
        if mode in _HEAD:
            self.blocks.append("#" * int(mode[1]) + " " + text)
        elif mode == "li":
            self.blocks.append("- " + text)
        elif len(text) >= 2:
            self.blocks.append(text)

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
            return
        if tag in _SKIP:
            self._skip += 1
            return
        if self._skip:
            return
        if tag == "img":                                  # 圖片→行內 markdown（spec 031 rich-paste）
            a = dict(attrs)
            src = a.get("src") or a.get("data-src") or a.get("data-actualsrc") or ""
            if src and src.startswith(("http", "//", "data:")):
                self._flush()
                if src.startswith("//"):
                    src = "https:" + src
                self.blocks.append(f"![{(a.get('alt') or '').strip()}]({src})")
            return
        if tag == "br":
            self._cur.append(" ")
        elif tag in _BLOCK:
            self._flush()
            self._mode = tag if tag in _HEAD else ("li" if tag == "li" else "p")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
            return
        if tag in _SKIP and self._skip:
            self._skip -= 1
            return
        if self._skip:
            return
        if tag in _BLOCK:
            self._flush()

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip and self._mode:
            self._cur.append(data)


def extract_article_markdown(html: str) -> tuple[str, str]:
    """回 (title, markdown)。抽不到→("", "")；不崩（best-effort）。"""
    p = _ArticleMarkdown()
    try:
        p.feed(html or "")
    except Exception:  # noqa: BLE001 - 壞 HTML 不該炸收進
        pass
    p._flush()
    title = " ".join(p.title.split()).strip()
    md = "\n\n".join(p.blocks).strip()
    return title, md
