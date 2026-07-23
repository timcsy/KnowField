"""拉取結果渲染（繁中）。散文文章＋圖；--raw 純標題＋來源＋連結、零生成文字（SC-006）。"""

from __future__ import annotations

import json

from ..pull.types import PullEntry, PullResult


def render(result: PullResult, fmt: str = "terminal", raw: bool = False) -> str:
    if fmt == "json":
        return _render_json(result, raw)
    is_md = fmt == "markdown"
    header = f"{'# ' if is_md else '🔎 '}主題「{result.topic}」拉取結果"
    lines = [header, ""]
    if result.is_empty:
        lines.append("（查無與此主題相關的材料。）")
    else:
        for e in result.entries:
            lines.extend(_entry_block(e, is_md, raw))
            lines.append("")
    if result.missing_sources:
        lines.append(f"⚠ 缺漏來源：{', '.join(result.missing_sources)}")
    if result.truncated_count:
        lines.append(f"（另有 {result.truncated_count} 則未納入，可調整上限）")
    return "\n".join(lines).rstrip() + "\n"


def _entry_block(e: PullEntry, is_md: bool, raw: bool) -> list[str]:
    lines: list[str] = []
    head = f"{'## ' if is_md else '• '}[{e.rank}] {e.item.title}"
    if raw or e.article is None:
        lines.append(head)
        lines.append(f"    原文：{e.item.url}")
        return lines
    a = e.article
    lines.append(head)
    if a.figure:
        if is_md:
            lines.append(f"![{a.figure.label()}]({a.figure.url})")
        else:
            lines.append(f"    圖：{a.figure.url}（{a.figure.label()}）")
    lines.append(a.body)
    lines.append(f"{'' if is_md else '    '}原文：{a.source_url}")
    return lines


def _render_json(result: PullResult, raw: bool) -> str:
    def entry(e: PullEntry) -> dict:
        d = {"rank": e.rank, "relevance_score": round(e.relevance_score, 4),
             "title": e.item.title, "url": e.item.url}
        if not raw and e.article is not None:
            d["article"] = e.article.body
            if e.article.figure:
                d["figure"] = {"kind": e.article.figure.kind,
                               "url": e.article.figure.url,
                               "label": e.article.figure.label()}
        return d

    payload = {
        "topic": result.topic,
        "is_empty": result.is_empty,
        "truncated_count": result.truncated_count,
        "missing_sources": result.missing_sources,
        "entries": [entry(e) for e in result.entries],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
