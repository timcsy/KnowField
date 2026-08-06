# Quickstart：Web 介面

證明 web 端到端可用。細節見 [data-model.md](./data-model.md)、[contracts/](./contracts/)。

## 前置
- `uv sync --extra web --extra dev`（裝 fastapi/uvicorn/jinja2/httpx）
- 先跑一次匯整讓首頁有料：`uv run knowfield digest`（離線亦可）
- 啟動：`uv run uvicorn knowfield.web.app:app --reload`，開 http://127.0.0.1:8000

## 驗證情境

### 情境 A — 首頁看今日匯整（US1）
開 `/`。**預期**：看到今日匯整，每則散文＋（有則）原文圖內嵌＋可點原文連結。

### 情境 B — 圖內嵌與 AI 圖標示（FR-003）
用含原文圖的樣本產匯整後開 `/`。**預期**：圖以 `<img>` 內嵌；若為 AI 圖，標「AI 示意・非原文」。

### 情境 C — 主題即時拉（US2）
開 `/pull?topic=agent`（或首頁輸入框送出）。**預期**：顯示該主題散文結果＋原文連結。

### 情境 D — 快取（FR-005／SC-004）
連續兩次 `/pull?topic=agent`。**預期**：第二次由快取回應，**未再呼叫後端**。

### 情境 E — 管理興趣（US3）
開 `/interests`，新增「LLM 推理」再刪除。**預期**：清單即時反映增／刪。

### 情境 F — RWD（FR-007／SC-003）
在手機寬度與桌面寬度開首頁。**預期**：皆正常排版，無破版、無橫向捲動。

### 情境 G — 後端失敗友善頁（FR-009／SC-005）
在後端隔離／注入失敗時開 `/pull?topic=…`。**預期**：看到**繁中友善提示**（可稍後重試／
用離線），**不是 500 堆疊**。

### 情境 H — 空狀態（FR-011）
無匯整時開 `/`；冷門主題拉取。**預期**：明確空狀態提示，不空白不報錯。

## 對應自動化測試（TDD）
- contract：`tests/contract/test_web_routes.py`（TestClient，路由 A–E、G）
- integration：`tests/integration/test_web_*.py`（快取、錯誤頁、空狀態）
- unit：`tests/unit/test_web_cache.py`、`test_web_views.py`

情境先寫成**失敗測試**（原則 I）。後端用 stub、匯整用樣本，離線確定性；RWD（情境 F）為
人工／視覺驗證（無法純程式斷言版面）。
