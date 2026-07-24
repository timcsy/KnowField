# Quickstart：驗證 web 搜尋（階段 9）

## 1. 離線（預設 stub）
```bash
uv run uvicorn learnnews.web.app:app     # 開 http://127.0.0.1:8000/search
```
未設搜尋金鑰 → 用離線 stub 回固定假結果；打任意 query 看結果列出。

## 2. 收進成種子
對一則結果按「收進」→ 走既有 ingest（成種子）→ 到「問答」問它 → 檢索得到。
未收進的結果不在知識庫（/library 看不到）。

## 3. 真實搜尋（可選）
```bash
# .env 設 LEARNNEWS_SEARCH_API_URL、LEARNNEWS_SEARCH_KEY（勿貼聊天/勿進版控）
```
打真實 query → 回開放網路結果；挑有價值的收進。

## 4. 誠實邊界
未設金鑰或後端失敗 → 友善繁中提示、頁面正常、無堆疊。

## 5. 測試
```bash
uv run pytest tests/unit/test_websearch.py tests/contract/test_web_search.py -q
uv run pytest -q      # 全套：新測綠燈 + 既有 190 不回歸
```

## 驗收對映
| 檢查 | 對映 |
|---|---|
| 搜尋列結果（標題/網址/摘要） | FR-001、SC-001、US1 |
| 收進成種子、ask 檢索得到；未收進不落庫 | FR-002/003、SC-002、US2 |
| 後端失敗友善繁中 | FR-005、SC-003、US3 |
| 可插拔離線可測、190 不回歸 | FR-004、SC-004 |
