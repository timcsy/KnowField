# Data Model：跟你的場聊天

**不改 schema、不新增資料表。** 對話短暫、不落庫；唯有人按冊封才寫既有 `why_nodes`。

## 新實體（記憶體/短暫）

### 對話訊息（`chat/field_chat.py`）
`dict{role: "user"|"assistant"|"system", content: str}` 的 list。歷史由 client（hidden field JSON）帶回，不落庫。

### `CandidateDraft`（冊封候選）
| 欄位 | 型別 | 說明 |
|------|------|------|
| `claim` | `str` | 根因主張（使用者語氣） |
| `ladder` | `list[str]` | 推導階梯（每階一個 why） |
| `evidence_urls` | `list[str]` | 佐證連結（可空） |
短暫、可編輯；**唯有人按「冊封」→** `add_why_node(claim, evidence_urls, [], False, 0, date, ladder)`+`anoint`。

## 沿用（不變）
- `WhyNode`（已冊封根因，讀場注入的場脈絡）／`list_why_nodes('anointed')`。
- `add_why_node`+`anoint_why_node`（人閘門寫回，spec 010/012）。
- `SearchResult`（佐證證據，spec 009）／`make_web_search`。

## 契約摘要
- `build_field_system_prompt(roots: list[WhyNode]) -> str`：膜指引＋場脈絡（roots claim＋ladder）。
- `ChatBackend.reply(messages) -> str`（Stub＋OpenAI）。
- `FieldChat.reply(history, user_msg, roots) -> str`；`FieldChat.distill(history, roots) -> CandidateDraft`。
