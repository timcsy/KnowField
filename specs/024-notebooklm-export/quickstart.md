# Quickstart: 匯出給 NotebookLM

## 前置
- 已在 `024-notebooklm-export`；`uv run pytest -q` 現 368 綠。
- 本功能只讀既有 `conversations`／`why_nodes`，無需 migration。

## 跑測試（TDD）
```bash
uv run pytest tests/unit/test_export_notebooklm.py tests/unit/test_export_web.py -q
uv run pytest -q     # 全套不回歸（368 →）
```

## 手動驗證（web）
```bash
KNOWFIELD_DB=knowfield.db uv run uvicorn knowfield.web.app:app --port 8000
```
1. **對話（存檔）**：開 `/conversations`→ 挑一段 → 按「📋 複製 Markdown」→ 貼到編輯器：應見標題、你／副手發言、逐訊息「來源：」清單、行內 `[n]` 對得上。按「🔗 複製佐證網址」→ 每行一個、去重的 URL。
2. **對話（live）**：`/chat` 聊幾句 → 兩顆鈕 → 內容與存檔後複製一致。
3. **根因**：`/roots` 任一條 → 「📋 複製 Markdown」得主張＋階梯＋佐證；「🔗 複製佐證網址」得該根因佐證 URL。
4. **貼進 NotebookLM**：Markdown → 新增「文字」來源；網址清單 → 新增「網站」來源（逐行）。

## 驗收對照（spec SC）
- SC-001/002：三頁各能一鍵複製 Markdown／佐證網址。
- SC-003：`test_export_notebooklm.py` 綠（空／缺欄位不崩）。
- SC-004：唯讀守衛測綠（匯出後 DB 與場脈絡不變）。
- SC-005：全繁中、核心零相依、368 不回歸＋新測。
