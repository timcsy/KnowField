"""行為校準（US3、FR-012）：由點擊訊號更新 learned_weights。

明講永遠優先：learned_weights 只加成明講清單中既有的主題（見 relevance.py 與
service.remove/set 的清理），被移除的主題不會因學習復活。
"""

from __future__ import annotations


def learn(topic_actions: list[tuple[str, str]]) -> dict[str, float]:
    """由 (主題, 動作) 列表計算學習權重。

    clicked 加分、skipped 扣分；正規化到 [0, 1]。回傳每主題的權重。
    """
    scores: dict[str, float] = {}
    for topic, action in topic_actions:
        delta = 1.0 if action == "clicked" else -0.5 if action == "skipped" else 0.0
        scores[topic] = scores.get(topic, 0.0) + delta
    if not scores:
        return {}
    max_score = max(scores.values())
    if max_score <= 0:
        return {t: 0.0 for t in scores}
    return {t: max(0.0, s / max_score) for t, s in scores.items()}


def merge_into_profile(
    explicit_topics: list[str], learned: dict[str, float]
) -> dict[str, float]:
    """只保留明講清單內的主題權重（明講優先）。"""
    return {t: w for t, w in learned.items() if t in explicit_topics}
