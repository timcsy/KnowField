# Phase 1 資料模型：可讀文章式消化

複用階段 1–4 實體（`Source`、`Item`、`EventCluster`、`Digest`、`PullResult`）。
本階段以 **Article 取代 Summary** 為預設消化產物。

## 新增/變更實體

### Article（消化文章）— 取代 Summary
一則材料的可讀散文消化。
- `item_id` → Item
- `body`：繁中散文正文（連貫段落，非列點；完整傳達重點/數據/適用時機）
- `source_url`：一鍵直達原文（FR-004，複製自 item.url，渲染必帶）
- `figure`：Figure | None（可選配圖）
- `degraded`：布林——若後端失敗降級為精簡呈現則為真（FR-011，可觀測）

**驗證**：
- `body` MUST 不含原文未提供的數據（FR-002，靠提示＋抽查，非程式可完全驗）
- `body` MUST 不含工具結論/外推（FR-003）
- 對應 `item.has_source_link()` 為真才產出（否則該則本就被排除）

### Figure（配圖）
- `kind`：`"原文"` | `"AI 示意"`
- `url`：圖片位址（原文圖 URL 或 AI 圖 URL）
- `source_note`：原文出處說明；`kind="AI 示意"` 時渲染 MUST 標「AI 示意・非原文」（FR-007）

**規則**：`kind="AI 示意"` 的圖在任何輸出格式都 MUST 帶明確標示，不得與原文圖混淆。

## 變更既有實體
- **DigestEntry / PullEntry**：`summary: Summary | None` → 改帶 `article: Article | None`
  （`--raw` 時為 None）。
- **digest_entries 表**：增欄位存文章正文與圖（`article_body`、`figure_url`、`figure_kind`），
  供 `pull --from-digest` 與日後回顧。
- **Summary（舊）**：保留供過渡/測試，不再是預設路徑。

## 資料流（文字）
```
進榜 Item（推 top-N / 拉結果）
  → ArticleBuilder：LLM 依原文生散文（忠實約束）→ body
  → 抓圖（best-effort）：原文圖 → Figure(原文)；無則（可選）AI 圖 → Figure(AI 示意)；再無 → None
  → Article(body, source_url, figure)
  失敗（後端/限流）→ 降級：article.degraded=True，body 退精簡（≈raw），不中斷
```
