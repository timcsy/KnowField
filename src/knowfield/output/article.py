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
    "3. 部落格教學語氣、繁體中文：**先用一段『引起動機』**（讀者常見的困惑／為何值得看），"
    "再用小節把脈絡串成一根脊椎，最後『一句話帶走』。少而深、收斂、別灌水。\n"
    "4. **只輸出正文**（不要寫 References／延伸閱讀，那些會由系統補）。")

# 長度／難度：影響 prompt 的指示（不是硬截斷）
_LENGTHS = {
    "short": "短（約 500 字，直接切重點、少鋪陳）",
    "medium": "中（約 1200 字，脈絡完整）",
    "long": "長（約 2500 字，深入鋪陳、多舉例）",
}
_LEVELS = {
    "intro": "入門（給初學者：多鋪陳、白話、少術語，必要時用比喻）",
    "intermediate": "進階（給有基礎的：可用術語，著重脈絡與關聯）",
    "expert": "專家（給熟悉者：精煉直接、著重洞見與非顯然的細節，假設懂基礎術語）",
}


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


def build_article_prompt(topic: str, body: list, length: str = "medium",
                         level: str = "intermediate") -> str:
    """給 LLM 的 user prompt：主題＋長度／難度＋編號的核心理解（含佐證脈絡）。"""
    lines = [f"主題：{topic}",
             f"長度：{_LENGTHS.get(length, _LENGTHS['medium'])}",
             f"難度：{_LEVELS.get(level, _LEVELS['intermediate'])}\n",
             "核心理解（只能用這些；標 [n] 引用）："]
    for i, w in enumerate(body, 1):
        lines.append(f"[{i}]（{getattr(w, 'kind', '')}）{getattr(w, 'claim', '')}")
    lines.append("\n請寫成一篇部落格教學文章（繁中），依鐵律與上面的長度／難度。")
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
                     top_k: int = 8, length: str = "medium", level: str = "intermediate",
                     pinned: list | None = None) -> dict:
    """從已冊封核心理解生成高證實文章。回 {title, markdown, empty}。length/level＝長度/難度。
    body＝相關度前 top_k 的 🔬🧩；ext＝相關的 🌉💭（延伸閱讀）。References 結構化組（原則 3）。

    `pinned`（spec 043）＝某段對話冊封出的核心理解：**必被考慮**，排在最前。

    ⚠️ 釘住只動「排序」這一步，**下面的 kind 分流與 top_k 一個字都不改**——
    所以 `猜想`／`類比` 就算被釘住也只會進延伸閱讀，進不了正文。
    釘的是「必被考慮」，不是「必進正文」：文章的整個賣點是高證實，
    讓釘住能繞過分層就等於自廢武功（實測 referrers 裡真的有 `猜想`）。

    為什麼不是「把 referrers 的內容當 topic 去檢索」：檢索沒選中是**沉默**的失敗
    ——你不會知道這段對話冊封出的東西沒被寫進去（`experience.md「一個機制的失敗如果是沉默的，就要另外給一條「我指定」的路」`）。
    """
    ranked = _rank_by_topic(nodes, topic, embedder)
    if pinned:
        seen = {id(w) for w in pinned}
        ranked = list(pinned) + [w for w in ranked if id(w) not in seen]
    body = [w for w in ranked if (getattr(w, "kind", "") or "") in _BODY_KINDS][:top_k]
    ext = [w for w in ranked if (getattr(w, "kind", "") or "") in _EXT_KINDS][:3]
    if not body:
        return {"title": topic, "markdown": "", "empty": True}
    article = (chat_backend.reply([{"role": "system", "content": _SYS},
                                   {"role": "user", "content": build_article_prompt(topic, body, length, level)}]) or "").strip()
    if not article:
        return {"title": topic, "markdown": "", "empty": True}
    parts = [article, _references(body)]
    reading = _extended_reading(ext)
    if reading:
        parts.append(reading)
    parts.append(_MEMBRANE_NOTE)
    return {"title": topic, "markdown": "\n\n".join(parts), "empty": False}
