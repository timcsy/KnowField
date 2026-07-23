"""匯整輸出渲染（繁中終端／Markdown／JSON）。散文文章＋圖；--raw 純原礦（FR-010）。"""

from __future__ import annotations

import json

from ..models import Digest, DigestEntry


def render(digest: Digest, fmt: str = "terminal", raw: bool = False) -> str:
    if fmt == "json":
        return _render_json(digest, raw)
    is_md = fmt == "markdown"
    header = f"{'# ' if is_md else '📰 '}{digest.date} 每日分診匯整"
    lines = [header, ""]
    if digest.is_empty:
        lines.append("（今日沒有符合你興趣的新條目。）")
    else:
        for e in digest.entries:
            lines.extend(_entry_block(e, is_md, raw))
            lines.append("")
    lines.extend(_footer(digest))
    return "\n".join(lines).rstrip() + "\n"


def _entry_block(e: DigestEntry, is_md: bool, raw: bool) -> list[str]:
    lines: list[str] = []
    if raw or e.article is None:
        lines.append(f"{'## ' if is_md else '• '}[{e.rank}] {e.item.title}")
        lines.append(f"    原文：{e.item.url}")
        return lines
    a = e.article
    lines.append(f"{'## ' if is_md else '• '}[{e.rank}] {e.item.title}")
    if a.figure:
        if is_md:
            lines.append(f"![{a.figure.label()}]({a.figure.url})")
        else:
            lines.append(f"    圖：{a.figure.url}（{a.figure.label()}）")
    lines.append(a.body)
    lines.append(f"{'' if is_md else '    '}原文：{a.source_url}")
    return lines


def _footer(digest: Digest) -> list[str]:
    lines: list[str] = []
    if digest.missing_sources:
        lines.append(f"⚠ 缺漏來源：{', '.join(digest.missing_sources)}")
    if digest.truncated_count:
        lines.append(f"（另有 {digest.truncated_count} 則未納入，可調整上限）")
    return lines


def _render_json(digest: Digest, raw: bool) -> str:
    def entry(e: DigestEntry) -> dict:
        d = {"rank": e.rank, "relevance_score": round(e.relevance_score, 4),
             "title": e.item.title, "url": e.item.url}
        if not raw and e.article is not None:
            d["article"] = e.article.body
            d["degraded"] = e.article.degraded
            if e.article.figure:
                d["figure"] = {"kind": e.article.figure.kind,
                               "url": e.article.figure.url,
                               "label": e.article.figure.label()}
        return d

    payload = {
        "date": digest.date,
        "is_empty": digest.is_empty,
        "truncated_count": digest.truncated_count,
        "missing_sources": digest.missing_sources,
        "entries": [entry(e) for e in digest.entries],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
