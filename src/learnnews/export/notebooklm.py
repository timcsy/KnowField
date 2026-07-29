"""NotebookLM 匯出 formatter（spec 024）。純函式：primitives 進、字串／清單出。

零相依、無副作用、離線可測、對缺項不拋例外（教訓 3）。只把已沉澱物匯出，不注入回場（原則 6）。
"""

from __future__ import annotations

_ROLE_LABEL = {"user": "你", "assistant": "副手"}


def dedup_urls(urls: list) -> list:
    """去重保序。"""
    seen: set = set()
    out: list = []
    for u in urls or []:
        u = (u or "").strip() if isinstance(u, str) else ""
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _sources_of(msg: dict) -> list:
    src = msg.get("sources") if isinstance(msg, dict) else None
    return src if isinstance(src, list) else []


def conversation_to_markdown(title: str, messages: list) -> str:
    """對話 → 乾淨 Markdown：標題＋逐則（依角色標示，保留行內 [n]）＋每則來源塊接其後。"""
    lines: list = [f"# {(title or '').strip() or '（未命名對話）'}", ""]
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        label = _ROLE_LABEL.get(msg.get("role"), "副手")
        content = (msg.get("content") or "").strip()
        lines.append(f"**{label}：** {content}".rstrip())
        srcs = _sources_of(msg)
        if srcs:
            lines.append("")
            lines.append("來源：")
            for s in srcs:
                if not isinstance(s, dict):
                    continue
                url = (s.get("url") or "").strip()
                n = s.get("n")
                label_txt = (s.get("title") or "").strip() or url
                if url:
                    prefix = f"- [{n}] " if n is not None else "- "
                    lines.append(f"{prefix}{label_txt} — {url}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def conversation_evidence_urls(messages: list) -> list:
    """跨全訊息收集所有來源 URL，去重保序。"""
    urls: list = []
    for msg in messages or []:
        for s in _sources_of(msg):
            if isinstance(s, dict) and (s.get("url") or "").strip():
                urls.append(s["url"].strip())
    return dedup_urls(urls)


def why_node_to_markdown(claim: str, ladder: list, evidence_urls: list) -> str:
    """根因 → Markdown：主張＋（有則）階梯數字列表＋（有則）佐證清單。空段略過。"""
    lines: list = [f"# {(claim or '').strip() or '（未命名根因）'}", ""]
    steps = [str(x).strip() for x in (ladder or []) if str(x).strip()]
    if steps:
        lines.append("## 為何（階梯：表面 → bedrock）")
        for i, step in enumerate(steps, 1):
            lines.append(f"{i}. {step}")
        lines.append("")
    urls = dedup_urls(evidence_urls or [])
    if urls:
        lines.append("## 佐證")
        for u in urls:
            lines.append(f"- {u}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
