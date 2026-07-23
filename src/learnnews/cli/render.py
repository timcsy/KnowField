"""匯整輸出渲染（繁中終端／Markdown／JSON）。面向使用者文字皆繁中（FR-010）。"""

from __future__ import annotations

import json

from ..models import Digest


def render(digest: Digest, fmt: str = "terminal") -> str:
    if fmt == "json":
        return _render_json(digest)
    if fmt == "markdown":
        return _render_markdown(digest)
    return _render_terminal(digest)


def _entry_lines(digest: Digest, bullet: str) -> list[str]:
    lines: list[str] = []
    for e in digest.entries:
        s = e.summary
        lines.append(f"{bullet} [{e.rank}] {s.positioning}")
        lines.append(f"    為何值得看：{s.why_worth}")
        lines.append(f"    原文：{e.item.url}")
    return lines


def _footer(digest: Digest) -> list[str]:
    lines: list[str] = []
    if digest.missing_sources:
        lines.append(f"⚠ 缺漏來源：{', '.join(digest.missing_sources)}")
    if digest.truncated_count:
        lines.append(f"（另有 {digest.truncated_count} 則未納入，可調整上限）")
    return lines


def _render_terminal(digest: Digest) -> str:
    header = f"📰 {digest.date} 每日分診匯整"
    if digest.is_empty:
        body = ["（今日沒有符合你興趣的新條目。）"]
    else:
        body = _entry_lines(digest, "•")
    return "\n".join([header, ""] + body + [""] + _footer(digest)).rstrip() + "\n"


def _render_markdown(digest: Digest) -> str:
    header = f"# {digest.date} 每日分診匯整"
    if digest.is_empty:
        body = ["_今日沒有符合你興趣的新條目。_"]
    else:
        body = _entry_lines(digest, "-")
    return "\n".join([header, ""] + body + [""] + _footer(digest)).rstrip() + "\n"


def _render_json(digest: Digest) -> str:
    payload = {
        "date": digest.date,
        "is_empty": digest.is_empty,
        "truncated_count": digest.truncated_count,
        "missing_sources": digest.missing_sources,
        "entries": [
            {
                "rank": e.rank,
                "relevance_score": round(e.relevance_score, 4),
                "title": e.item.title,
                "url": e.item.url,
                "positioning": e.summary.positioning,
                "why_worth": e.summary.why_worth,
            }
            for e in digest.entries
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
