"""spec 032：收進的活化——把一份收進來源整理成候選核心理解。

母概念 concepts/有吸引子的場：這是「外部證言 →（人閘門）→ 地基」的橋。
- 只產**候選**（status=candidate）；冊封由人（原則 5/6，本函式不冊封、不進地基）。
- 復用 rootcause.extract（7 條試金石自我反駁＋ladder＋fog_flag）；來源 url 存進候選的
  evidence_urls＝源→根因的「由來」連結（教訓 8：零 schema 改動）。
- extractor 可注入離線 stub（教訓 1）；萃取失敗拋 SourceUnavailable（route 攔成友善繁中）。
"""

from __future__ import annotations

import re

from ..rootcause.extract import Candidate, RootCauseExtractor

_PAGE_RE = re.compile(r"<!--kf-page:(\d+)-->")


def _strip_pages(body: str) -> str:
    """去掉 PDF 頁碼標記（給 AI 抽取／錨點用，別讓標記污染）。"""
    return _PAGE_RE.sub("", body or "")


def _quote_page(raw: str, quote: str) -> int:
    """錨點落在第幾頁：raw（含頁碼標記）中 quote 位置前最後一個 <!--kf-page:N-->。無→0。"""
    pos = (raw or "").find(quote or "")
    if pos < 0 or not quote:
        return 0
    page = 0
    for m in _PAGE_RE.finditer(raw):
        if m.start() > pos:
            break
        page = int(m.group(1))
    return page


def _source_anchor(body: str) -> str:
    """從來源正文取一段 verbatim 錨點（Text Fragment `#:~:text=` 用，定位回原文段落）：
    第一個夠長的實質句子，跳過標題/表格/公式/圖/清單/頁碼標記。取不到→空（由來退回整篇）。
    刻意取**較短**（≤90 字、切在詞界）——太長會跨行內元素/腳註而配不到（TF best-effort）。"""
    for para in (body or "").split("\n\n"):
        p = para.strip()
        if not p or p[0] in "#|-*>" or p.startswith(("$$", "![", "<!--")):
            continue
        s = re.split(r"(?<=[。.!?])\s", p, maxsplit=1)[0].strip()
        if len(s) < 24:
            continue
        if len(s) > 90:                       # 截短、切在詞界（英文；中文無空格則直接截）
            cut = s[:90]
            sp = cut.rfind(" ")
            s = cut[:sp] if sp > 40 else cut
        return s
    return ""


def distill_source(repo, extractor: RootCauseExtractor, url: str,
                   now: str = "") -> Candidate | None:
    """讀一來源的塊 → 抽候選根因 → 存成候選 why-node（evidence=[url]）。

    回候選 Candidate；來源沒內容、或挖不到有把握的根因（no_material／空 claim）→ 回 None
    （不硬編一個假洞見，原則 6）。萃取後端失敗 → 讓 SourceUnavailable 冒出，由 route 攔。
    """
    chunks = repo.get_source_chunks(url)
    raw = "\n\n".join(c for c in chunks if c).strip()   # 含頁碼標記（PDF）
    body = _strip_pages(raw).strip()                    # 去標記→給 AI 抽取／錨點
    if not body:
        return None
    title = repo.source_title(url)
    cand = extractor.extract(title, body)
    if cand.no_material or not (cand.claim or "").strip():
        return None
    anchor = _source_anchor(body)
    repo.add_why_node(cand.claim, [url], cand.touchstones, cand.fog_flag,
                      0, now, ladder=cand.ladder,
                      source_quote=anchor, source_page=_quote_page(raw, anchor))
    return cand
