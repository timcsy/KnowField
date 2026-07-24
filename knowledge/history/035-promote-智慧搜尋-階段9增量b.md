# 035：promote 智慧搜尋 → vision 階段 9 增量 b

> 日期：2026-07-25　｜　承接 history/034（web 搜尋完成）

## 轉移
web 搜尋（階段 9）真跑通後，使用者對比「你（助理）的 Web Search 也會做**處理和探索**」，問
`/search` 能不能有智慧處理、別只倒 Tavily 原始結果。→ capture 成 `draft/2026-07-25-智慧搜尋.md`
（`c3d8114`）→ knowie-next 評估 → **promote 成 vision 階段 9 增量 b**。使用者選「智慧搜尋先」
（優先於 2b 根因萃取）。

## 決策
- **核心（本增量）＝「處理」**：抓 top-N 結果內文 → RAG answerer 合成繁中「整理」（逐點 `[n]`
  掛結果）→ 依相關度排序。＝把原則 4「消化到底」套到 live 搜尋流＝**RAG over 搜尋結果**。
- **探索（multi-angle／agentic）列 optional、未 promote**——成本翻倍（多次搜尋＋多輪 LLM），
  另列里程碑。先處理、後探索（處理都還沒有，先把它做出來）。

## 為何這樣切（三面對齊）
- **principles**：原則 4 消化到底（整理）、原則 3 溯源（`[n]` 掛結果）、原則 5 人挑（收進不變）。
- **experience**：教訓 7 grounding——整理復用 `RagService._is_no_material`／grounded answerer，
  「只根據材料、不杜撰」是**程式結構保證**非提示自律。
- **復用密度極高**：`fetch_url`（seed/fetch.py:92）、`Answerer.answer`（rag/answerer.py:15）、
  Embedder＋cosine、`/search`／`search.html`（spec 009）全現成，新工只是串接、零新核心。

## 其他路線（否決）
- 純 snippet 合成（不抓內文）：省但整理淺、易失真 → 否決，抓 top-N 內文。
- 直接做探索：處理都還沒有、成本翻倍 → 先處理。

## 出口
- draft **不刪**（in-flight rationale，探索段標 optional-未 promote），完成後 reflow＋retire。
- 下一步：`/speckit-specify` 開 spec 010（智慧搜尋）。驗收見 vision 階段 9 增量 b。
