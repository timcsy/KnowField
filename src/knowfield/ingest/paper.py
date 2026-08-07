"""論文來源加料（先 arXiv）：抓乾淨 metadata（Abstract/作者/日期）＋原始 PDF，存進 /media 供論文展示。

母概念：來源＝原文為真相、抽取為檢索參考（`history/082`）。論文（尤其 arXiv）有現成的乾淨 Abstract＋PDF，
特別值得「真相」展示。best-effort：抓不到不擋收進（教訓 3）。arXiv API：export.arxiv.org/api/query。
"""
from __future__ import annotations

import re
import urllib.request

_ARXIV_ID = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d+\.\d+)(?:v\d+)?", re.I)


def arxiv_id(url: str) -> str:
    """從來源 url 抽 arXiv id（無→空）。"""
    m = _ARXIV_ID.search(url or "")
    return m.group(1) if m else ""


def _first(pattern: str, text: str) -> str:
    m = re.search(pattern, text or "", re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def parse_arxiv_atom(xml: str) -> dict | None:
    """解析 arXiv API 的 Atom XML → {title, authors, abstract, published}。抽不到標題/摘要→None。"""
    m = re.search(r"<entry>(.*?)</entry>", xml or "", re.S)   # 只看 entry（feed 本身也有 title）
    entry = m.group(1) if m else (xml or "")
    title = _first(r"<title[^>]*>(.*?)</title>", entry)
    abstract = _first(r"<summary[^>]*>(.*?)</summary>", entry)
    if not title or not abstract:
        return None
    authors = [re.sub(r"\s+", " ", a).strip()
               for a in re.findall(r"<name>(.*?)</name>", entry, re.S)]
    published = _first(r"<published>(.*?)</published>", entry)[:10]   # YYYY-MM-DD
    return {"title": title, "authors": authors, "abstract": abstract,
            "published": published, "source": "arxiv"}


def fetch_arxiv_meta(aid: str, http_get=None) -> dict | None:
    """抓 arXiv metadata（best-effort，可注入 http_get 供離線測）。"""
    if not aid:
        return None
    url = f"http://export.arxiv.org/api/query?id_list={aid}"
    try:
        if http_get:
            xml = http_get(url)
        else:
            with urllib.request.urlopen(url, timeout=30) as r:
                xml = r.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 - 抓不到不擋收進
        return None
    return parse_arxiv_atom(xml or "")


def enrich_arxiv(media_dir: str, store_url: str, http_get=None, fetch_pdf_bytes=None) -> None:
    """arXiv 來源加料：存 metadata JSON＋原始 PDF 進 media_dir（論文展示＋防失效）。best-effort。"""
    from .media import save_paper_meta, save_source_pdf
    aid = arxiv_id(store_url)
    if not aid:
        return
    meta = fetch_arxiv_meta(aid, http_get)
    if meta:
        save_paper_meta(media_dir, store_url, meta)
    pdf_url = f"https://arxiv.org/pdf/{aid}"
    try:
        if fetch_pdf_bytes:
            data = fetch_pdf_bytes(pdf_url)
        else:
            with urllib.request.urlopen(pdf_url, timeout=120) as r:
                data = r.read()
        if data:
            save_source_pdf(media_dir, store_url, data)
    except Exception:  # noqa: BLE001 - PDF 抓不到不擋
        pass
