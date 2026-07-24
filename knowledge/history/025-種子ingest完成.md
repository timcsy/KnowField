# 025：種子 ingest 完成——第一個「深度吸引子」可冊封
> 日期：2026-07-24

## 轉移
走完 spec-kit 做出 spec 006 增量 2a：`ingest <arXiv-id|url> [--explainer]` 把手挑材料收進 KB
成「種子」。這是原則 5「權重由人冊封」的**第一個具體動作**落地。

- **交付**：`seed/{fetch,service}`（依 id/url 抓單篇、交易式 ingest）、`ingest` 指令、
  `digest_entries +source_class`（含既有 db migration）、種子容器 digest、解說文權重
  （`cosine×權重`，門檻仍原始 cosine）。
- **測試**：+14（unit fetch、integration 檢索/去重/權重、contract ingest/邊界）；**147→161 綠、零回歸**。
- **真跑**：arXiv id_list 抓取路徑真跑驗證（真標題「Attention Is All You Need」/摘要/裸 id url）。
  **完整 ingest→ask 真跑留使用者**（原則 5——收哪篇由人冊封＋消化額度）。

## 關鍵設計取捨（研究 R1）
種子存進**哨兵「種子容器」digest**（假裝成 digest）而非獨立 `seeds` 表——為的是**復用
`digest_entries`→`entry_id` 仍唯一→增量 1 的 `entry_embeddings` 免動免遷移**。語義略醜，
換來零侵入已出貨的增量 1。→ 蒸餾成 experience 教訓候選（見 experience）。

## knowie 對映（原則在程式兌現）
- 原則 5 人冊封（`ingest` 只收使用者指定、不認 canon）；原則 3 溯源（種子掛原文連結）；
  concept「種子＝深度吸引子」；教訓 1（http_get 可注入離線測）/3（失敗攔截不半殘）/4（沿用門檻）。

## draft 去留
RAG draft **不退場**——增量 2a 完成，但增量 2b（根因萃取）／增量 3 仍 in-flight。

## 狀態
✅ 增量 2a 完成（實作＋離線驗證＋arXiv 抓取真跑；完整真跑待使用者）
