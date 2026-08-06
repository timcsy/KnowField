"""spec 032：收進的活化——把一份收進來源整理成候選核心理解。

母概念 concepts/有吸引子的場：這是「外部證言 →（人閘門）→ 地基」的橋。
- 只產**候選**（status=candidate）；冊封由人（原則 5/6，本函式不冊封、不進地基）。
- 復用 rootcause.extract（7 條試金石自我反駁＋ladder＋fog_flag）；來源 url 存進候選的
  evidence_urls＝源→根因的「由來」連結（教訓 8：零 schema 改動）。
- extractor 可注入離線 stub（教訓 1）；萃取失敗拋 SourceUnavailable（route 攔成友善繁中）。
"""

from __future__ import annotations

from ..rootcause.extract import Candidate, RootCauseExtractor


def distill_source(repo, extractor: RootCauseExtractor, url: str,
                   now: str = "") -> Candidate | None:
    """讀一來源的塊 → 抽候選根因 → 存成候選 why-node（evidence=[url]）。

    回候選 Candidate；來源沒內容、或挖不到有把握的根因（no_material／空 claim）→ 回 None
    （不硬編一個假洞見，原則 6）。萃取後端失敗 → 讓 SourceUnavailable 冒出，由 route 攔。
    """
    chunks = repo.get_source_chunks(url)
    body = "\n\n".join(c for c in chunks if c).strip()
    if not body:
        return None
    title = repo.source_title(url)
    cand = extractor.extract(title, body)
    if cand.no_material or not (cand.claim or "").strip():
        return None
    repo.add_why_node(cand.claim, [url], cand.touchstones, cand.fog_flag,
                      0, now, ladder=cand.ladder)
    return cand
