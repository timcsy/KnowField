# 024：promote 增量 2a（種子 ingest）＋把增量 2 拆 2a/2b
> 日期：2026-07-24

## 轉移
`/knowie-next` 規劃後使用者確認 promote。原 vision 增量 2 綁三件（種子 ingest＋解說文＋根因
萃取）**太大**，且根因萃取最危險（plausible-BS 污染場）→ **拆兩層**：

- **增量 2a（已 commit）**：種子 ingest——人冊封第一個「深度吸引子」。`ingest <arXiv-id|url>`
  抓單篇→消化→嵌入→存為 KB 種子；解說文成獨立來源類＋品質權重（「一篇打敗五十篇」）。
- **增量 2b（未 commit）**：根因萃取（試金石＋信心層級＋人冊封）——碰「吸引子本體」，最需紀律。

拆法理由：**先鋪材料層（機械、低風險），再上判斷層（AI、高風險）**；2b 也需先有種子材料才萃取。

## 前置缺口（照 code 驗，2a 要處理）
- 種子沒有家：`list_corpus_entries` 只讀 `digest_entries`（種子要能成 corpus entry）。
- 無「依 ID/URL 抓單篇」：arXiv adapter 只依類別查。
- sources 有 `type` 無品質權重。
（複用現成：ArticleBuilder 消化、ensure_embeddings、RagService＋CLI/web ask。）

## knowie 對映
- **原則 5「權重由人冊封」**：種子 ingest＝人冊封吸引子的第一個具體動作。
- concept「種子＝深度吸引子」；原則 3 溯源、原則 4 消化到底（種子可全文）。

## 雙向連結
vision 增量 2a ↔ `draft/2026-07-24-RAG問答.md`（draft 不刪，續作 2b/3 的 in-flight 理由）。

## 下一步
`/speckit-specify` 開增量 2a 規格，走 TDD。cautions 帶入：原則 3（種子掛來源）、教訓 1（離線
stub 抓取可注入）、教訓 3（抓取失敗攔友善繁中）、教訓 4（沿用增量 1 校準門檻）。

## 狀態
✅ 增量 2a 已 promote（使用者 2026-07-24 確認）
