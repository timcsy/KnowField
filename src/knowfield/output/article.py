"""知識的輸出（vision 階段 30 第一刀 B）：從場的核心理解生成「高證實文章」。

母概念：來源＝原文為真相、抽取為參考（`history/082`）的**輸出面**——文章＝核心理解的**再表達**。
守衛（vision 階段 30／原則 3、6）：
- **正文只採 🔬已證實＋🧩推論**；🌉類比／💭猜想 隔到「延伸閱讀」並標明（別當定論）。
- **溯源靠結構**（原則 3，不靠模型自律）：References 由程式從核心理解的佐證 url **確定性組**，
  LLM 只寫正文＋[n] 上標，不自己編引用。
- 文章是**輸出物、不自動回灌場**（原則 6，馬太陷阱/model collapse 防線）——回場另走人閘門。
LLM 只負責「把提供的理解寫成流暢教學文」；事實邊界由「只餵這些理解」框住（反逢迎的膜）。
"""
from __future__ import annotations

from ..ranking.embeddings import cosine

_BODY_KINDS = {"已證實", "推論"}          # 進正文（高證實）
_EXT_KINDS = {"類比", "猜想"}             # 隔到延伸閱讀（想更遠、別當定論）

_SYS = (
    "你是把一個人自己冊封的『核心理解』寫成部落格教學文章的寫手。鐵律：\n"
    "1. **只根據下面編號的核心理解**寫，不要新增它們沒有的事實、不要杜撰。\n"
    "2. 用到某條理解時，在該句後標 **[n] 上標**（n＝理解編號；同一條可重複引用同編號）。\n"
    "3. 部落格教學語氣、繁體中文：**先用一段較長的『引起動機』**（讀者常見的困惑／為何值得看），"
    "再用小節把脈絡串成一根脊椎，最後『一句話帶走』。少而深、收斂、別灌水。\n"
    "4. **只輸出正文**（不要寫 References／延伸閱讀，那些會由系統補）。")


def _rank_by_topic(nodes: list, topic: str, embedder) -> list:
    """依與主題的語意相關度排序（有 embedder 才排；否則原序）。"""
    if not embedder or not (topic or "").strip() or not nodes:
        return list(nodes)
    try:
        tv = embedder.embed(topic)
        cvs = embedder.embed_many([getattr(w, "claim", "") for w in nodes])
        order = sorted(range(len(nodes)), key=lambda i: -cosine(tv, cvs[i]))
        return [nodes[i] for i in order]
    except Exception:  # noqa: BLE001 - 排序失敗→原序（不擋生成）
        return list(nodes)


def build_article_prompt(topic: str, body: list) -> str:
    """給 LLM 的 user prompt：主題＋編號的核心理解（含佐證脈絡）。"""
    lines = [f"主題：{topic}\n", "核心理解（只能用這些；標 [n] 引用）："]
    for i, w in enumerate(body, 1):
        lines.append(f"[{i}]（{getattr(w, 'kind', '')}）{getattr(w, 'claim', '')}")
    lines.append("\n請寫成一篇部落格教學文章（繁中），依鐵律。")
    return "\n".join(lines)


def _references(body: list) -> str:
    lines = ["#### References"]
    for i, w in enumerate(body, 1):
        ev = (getattr(w, "evidence_urls", None) or [""])[0]
        lines.append(f"{i}. {ev if ev.startswith('http') else '（你收藏的來源）'}")
    return "\n".join(lines)


def _extended_reading(ext: list) -> str:
    if not ext:
        return ""
    lines = ["#### 延伸閱讀（你場裡相鄰、想更遠可往這走）"]
    for w in ext:
        ev = (getattr(w, "evidence_urls", None) or [""])[0]
        tag = "🌉 類比" if getattr(w, "kind", "") == "類比" else "💭 猜想"
        link = f" · {ev}" if ev.startswith("http") else ""
        lines.append(f"- {getattr(w, 'claim', '')[:90]}〔{tag}{link}〕")
    return "\n".join(lines)


_MEMBRANE_NOTE = ("<sub>正文只採你場中「已證實／推論」層；延伸閱讀才放類比／猜想，並標明"
                  "——想更遠、但別當定論。</sub>")


def generate_article(topic: str, nodes: list, chat_backend, embedder=None,
                     top_k: int = 8) -> dict:
    """從已冊封核心理解生成高證實文章。回 {title, markdown, empty}。
    body＝相關度前 top_k 的 🔬🧩；ext＝相關的 🌉💭（延伸閱讀）。References 結構化組（原則 3）。"""
    ranked = _rank_by_topic(nodes, topic, embedder)
    body = [w for w in ranked if (getattr(w, "kind", "") or "") in _BODY_KINDS][:top_k]
    ext = [w for w in ranked if (getattr(w, "kind", "") or "") in _EXT_KINDS][:3]
    if not body:
        return {"title": topic, "markdown": "", "empty": True}
    article = (chat_backend.reply([{"role": "system", "content": _SYS},
                                   {"role": "user", "content": build_article_prompt(topic, body)}]) or "").strip()
    if not article:
        return {"title": topic, "markdown": "", "empty": True}
    parts = [article, _references(body)]
    reading = _extended_reading(ext)
    if reading:
        parts.append(reading)
    parts.append(_MEMBRANE_NOTE)
    return {"title": topic, "markdown": "\n\n".join(parts), "empty": False}
