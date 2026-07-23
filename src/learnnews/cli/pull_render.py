"""拉取結果渲染（繁中）。--raw 時純標題＋來源＋連結、零生成文字（SC-007）。"""

from __future__ import annotations

import json

from ..pull.types import PullResult


def render(result: PullResult, fmt: str = "terminal", raw: bool = False) -> str:
    if fmt == "json":
        return _render_json(result, raw)
    header_char = "#" if fmt == "markdown" else "🔎"
    bullet = "-" if fmt == "markdown" else "•"
    header = f"{header_char} 主題「{result.topic}」拉取結果"
    lines = [header, ""]
    if result.is_empty:
        lines.append("（查無與此主題相關的材料。）")
    else:
        for e in result.entries:
            if raw or e.summary is None:
                lines.append(f"{bullet} [{e.rank}] {e.item.title}")
            else:
                lines.append(f"{bullet} [{e.rank}] {e.summary.positioning}")
            lines.append(f"    原文：{e.item.url}")
    lines.append("")
    if result.missing_sources:
        lines.append(f"⚠ 缺漏來源：{', '.join(result.missing_sources)}")
    if result.truncated_count:
        lines.append(f"（另有 {result.truncated_count} 則未納入，可調整上限）")
    return "\n".join(lines).rstrip() + "\n"


def _render_json(result: PullResult, raw: bool) -> str:
    payload = {
        "topic": result.topic,
        "is_empty": result.is_empty,
        "truncated_count": result.truncated_count,
        "missing_sources": result.missing_sources,
        "entries": [
            {
                "rank": e.rank,
                "relevance_score": round(e.relevance_score, 4),
                "title": e.item.title,
                "url": e.item.url,
                **({} if raw or e.summary is None
                   else {"positioning": e.summary.positioning}),
            }
            for e in result.entries
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
