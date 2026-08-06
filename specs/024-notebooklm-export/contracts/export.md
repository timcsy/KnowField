# Contracts: 匯出給 NotebookLM

## A. 純 formatter 契約（`src/knowfield/export/notebooklm.py`，零相依）

所有函式收基本型別、無副作用、離線可測、對缺項不拋例外。

### `conversation_to_markdown(title: str, messages: list[dict]) -> str`
- 組出對話 Markdown：標題（`# {title}`，空標題用「（未命名對話）」）；每則依角色標「**你：**」／「**副手：**」；assistant 內文保留行內 `[n]`；每則若有 `sources` 於其後附「來源：」清單（`- [n] {title} — {url}`，缺 title 用 url）。
- 邊界：空 messages → 只回標題行；缺 `content` → 視為空字串；缺 `sources` → 無來源塊。

### `conversation_evidence_urls(messages: list[dict]) -> list[str]`
- 跨全訊息收集 `sources[*].url`，**去重保序**回 list。無 url 的 source 略過；無來源 → `[]`。

### `why_node_to_markdown(claim: str, ladder: list[str], evidence_urls: list[str]) -> str`
- 組出根因 Markdown：`# {claim}`；有 ladder → 「## 為何（階梯：表面 → bedrock）」數字列表；有 evidence_urls → 「## 佐證」清單。空段略過。空 claim → 「（未命名根因）」。

### `dedup_urls(urls: list[str]) -> list[str]`
- 去重保序（供根因佐證與內部共用）。

## B. 端點契約（`src/knowfield/web/app.py`）

三端點皆回 `text/plain; charset=utf-8`（非 HTML）。`as` 參數：`md`（預設）｜`urls`。

### `POST /chat/export`
- 表單：`history`（JSON，前端 live 對話）、`as`、（可選）`title`。
- 行為：`_parse_history(history)` → 依 `as` 回 `conversation_to_markdown(title, msgs)` 或 `"\n".join(conversation_evidence_urls(msgs))`。
- 空/壞 history → 回合理空輸出（不 500）。

### `GET /conversations/{cid}/export?as=md|urls`
- `repo.get_conversation(cid)`；不存在 → 404。存在 → 依 `as` 回 Markdown 或網址清單（`text/plain`）。

### `GET /roots/{wid}/export?as=md|urls`
- 自 `repo.list_why_nodes()` 取 `id==wid` 者；不存在 → 404。依 `as` 回 `why_node_to_markdown(...)` 或網址清單。

**唯讀**：三端點皆不寫庫、不改場、不觸 `build_field_system_prompt`（守衛測）。

## C. 前端契約（模板）

- `base.html`：共用 `copyExport(url, opts)`——`fetch`（GET 或帶 body 的 POST）取 `text` → `navigator.clipboard.writeText(text)` → 顯示 toast「已複製，可貼進 NotebookLM」；失敗 → 明確繁中提示。
- `chat.html`：兩顆鈕呼叫 `POST /chat/export`（帶當前 `history_json`＋`as`）。
- `conversation.html`：兩顆鈕呼叫 `GET /conversations/{id}/export?as=…`。
- `roots.html`：每條根因兩顆鈕呼叫 `GET /roots/{w.id}/export?as=…`。
- 全繁中；鈕：`📋 複製 Markdown`、`🔗 複製佐證網址`。

## D. 測試契約

- **單元**（`test_export_notebooklm.py`）：4 函式 ×（正常／空／無來源／缺欄位／重複去重）。
- **web**（`test_export_web.py`）：3 端點 × 2 格式回正確 `text/plain`；不存在 → 404；**唯讀守衛**：呼叫後 DB 內容不變、`build_field_system_prompt` 不受影響。
