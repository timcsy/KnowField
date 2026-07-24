"""種子抓取：依 arXiv ID 或 URL 抓單篇 → Item。`http_get` 可注入（離線可測，教訓 1）。"""

from __future__ import annotations

import re
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

from ..models import Item
from ..sources.base import SourceUnavailable

_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV_ID = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?", re.I)


def normalize_arxiv_id(ref: str) -> str | None:
    """從各種寫法抽出裸 arXiv id（去版本）；非 arXiv 回 None。

    接受：`2407.12345`、`2407.12345v2`、`arXiv:2407.12345`、`https://arxiv.org/abs/2407.12345`。
    """
    ref = (ref or "").strip()
    low = ref.lower()
    is_arxiv = "arxiv" in low or "/abs/" in low or re.fullmatch(
        r"\d{4}\.\d{4,5}(v\d+)?", ref) is not None
    if not is_arxiv:
        return None
    m = _ARXIV_ID.search(ref)
    return m.group(1) if m else None


def default_http_get(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LearnNews/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 - 統一轉成友善的來源不可用
        raise SourceUnavailable(f"取得失敗：{e}") from e


def fetch_arxiv_by_id(arxiv_id: str, http_get=default_http_get) -> Item:
    """依 arXiv id 抓單篇（id_list API），複用 Atom 解析。"""
    raw = http_get(f"https://export.arxiv.org/api/query?id_list={arxiv_id}")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise SourceUnavailable(f"arXiv 回應無法解析：{e}") from e
    entry = root.find(f"{_ATOM}entry")
    if entry is None:
        raise SourceUnavailable(f"arXiv 查無此 id：{arxiv_id}")
    title = " ".join((entry.findtext(f"{_ATOM}title") or "").split()).strip()
    summary = (entry.findtext(f"{_ATOM}summary") or "").strip()
    if not title:
        raise SourceUnavailable(f"arXiv 條目無標題：{arxiv_id}")
    return Item(source_id="seed", external_id=arxiv_id, title=title,
                abstract=summary, url=f"https://arxiv.org/abs/{arxiv_id}", lang="en")


class _TextExtractor(HTMLParser):
    """淺抽：<title> ＋ 較長的段落文字（略過 script/style/nav 等）。"""

    _SKIP = {"script", "style", "nav", "header", "footer", "aside"}

    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._in_title = False
        self._skip = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        if tag in self._SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in self._SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._skip == 0:
            t = " ".join(data.split())
            if len(t) >= 30:                 # 段落級文字，濾掉零碎導覽字
                self.chunks.append(t)


def fetch_url(url: str, http_get=default_http_get) -> Item:
    """抓一般文章 URL，淺抽 title＋主文（abstract 級；深 readability 為後續升級）。"""
    raw = http_get(url)
    p = _TextExtractor()
    try:
        p.feed(raw)
    except Exception as e:  # noqa: BLE001
        raise SourceUnavailable(f"頁面無法解析：{e}") from e
    title = " ".join(p.title.split()).strip()
    body = "\n".join(p.chunks)[:4000].strip()
    if not title or not body:
        raise SourceUnavailable("頁面取不到標題或正文")
    return Item(source_id="seed", external_id="", title=title, abstract=body, url=url)
