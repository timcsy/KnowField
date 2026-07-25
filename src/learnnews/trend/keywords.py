"""趨勢讀數（spec 013／階段 11）：從匯整標題統計當前高頻主題詞（熱詞）。

純函式、純標準函式庫（`re`/`collections`）——零外部呼叫、零相依、離線可測（教訓 1）。
趨勢＝盆地通量（concepts/有吸引子的場）：對已抓材料的**描述性**讀數，不預言。熱詞可回溯真實
材料（點擊 → /pull 深挖，原則 3）。MVP 純統計，無 LLM 幻覺風險；LLM 萃取留後續。

斷詞：英文詞（len≥2）＋中文相鄰雙字 bigram（既有 tokenize 把中文拆單字、不成主題詞，故自寫）。
"""

from __future__ import annotations

import re
from collections import Counter

_EN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+\-.]*")
_CJK_RE = re.compile(r"[一-鿿]")

# 停用詞：英文常見＋中文常見＋領域泛詞（幾乎每篇都有、無辨識度，FR-007）
STOPWORDS = {
    # 英文常見
    "the", "a", "an", "of", "for", "to", "and", "or", "with", "on", "in", "at",
    "by", "is", "are", "be", "new", "using", "use", "via", "from", "how", "we",
    "our", "you", "your", "it", "its", "as", "this", "that", "can", "will",
    # 領域泛詞（英）
    "model", "models", "method", "methods", "paper", "learning", "ai", "llm",
    "llms", "deep", "neural", "network", "networks", "approach", "based",
    "towards", "toward", "study", "analysis", "framework", "system", "systems",
    # 中文常見＋領域泛詞
    "的", "了", "在", "是", "和", "與", "及", "或", "一個", "如何", "我們",
    "這個", "這些", "可以", "使用", "模型", "方法", "研究", "系統", "架構",
    "分析", "學習", "技術", "應用", "問題", "能否", "透過", "基於",
}


def _terms(title: str) -> list[str]:
    """一個標題 → 候選詞（英文詞小寫、len≥2）＋（中文相鄰 bigram）。"""
    out: list[str] = []
    out.extend(t.lower() for t in _EN_RE.findall(title or "") if len(t) >= 2)
    chars = _CJK_RE.findall(title or "")
    # 相鄰雙字 bigram（同一標題內連續 CJK 字；跨非 CJK 斷開由 findall 已濾）
    for m in re.finditer(r"[一-鿿]{2,}", title or ""):
        run = m.group(0)
        for i in range(len(run) - 1):
            out.append(run[i:i + 2])
    return out


def trend_keywords(titles: list[str], top_n: int = 8,
                   stopwords: set | None = None, min_count: int = 2) -> list[str]:
    """回排序後的熱詞（高頻在前、同分保首次出現順序）。純函式、零 IO。"""
    stop = STOPWORDS | (stopwords or set())
    counts: Counter = Counter()
    first_seen: dict[str, int] = {}
    idx = 0
    for title in titles:
        for term in _terms(title):
            if term in stop:
                continue
            counts[term] += 1
            if term not in first_seen:
                first_seen[term] = idx
                idx += 1
    # 門檻＋排序：count 降序、同分依首次出現升序（stable、可重現）
    kept = [(t, c) for t, c in counts.items() if c >= min_count]
    kept.sort(key=lambda tc: (-tc[1], first_seen[tc[0]]))
    return [t for t, _ in kept[:top_n]]
