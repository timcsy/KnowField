# HTTP 路由契約：Web 介面

FastAPI 路由。測試以 `TestClient` 驗證（`tests/contract/test_web_routes.py`）。所有頁面
繁中、RWD；後端失敗經例外處理器攔成友善頁面（不 500）。

## `GET /` — 今日匯整（US1）
- **行為**：讀最近落庫匯整（`get_last_digest()`）渲染散文＋圖內嵌＋一鍵原文。
- **回應**：200 HTML。每則含標題、（有則）內嵌 `<img>`、散文段落、原文 `<a>`。
  無匯整 → 200 空狀態頁（提示去產生）。
- **契約測試**：
  - 有匯整 → 頁面含每則原文連結（FR-002）；有原文圖者含 `<img src=…>`（FR-003）。
  - AI 圖 → 頁面含「AI 示意・非原文」（FR-003）。
  - 無匯整 → 200 且顯示空狀態（FR-011）。

## `GET /pull?topic=<主題>` — 即時拉（US2）
- **行為**：正規化主題 → 快取命中回快取；否則 `run_pull` → 存快取 → 渲染。
- **回應**：200 HTML，散文結果＋原文連結；無結果 → 空狀態；載入以同步渲染完成即回。
- **契約測試**：
  - 給定主題 → 回該主題結果、每則有原文連結。
  - **同主題二次請求 → 不再呼叫後端**（快取命中，FR-005/SC-004；以 spy/計數驗證）。
  - 冷門主題 → 空狀態（FR-011）。

## `GET /interests`、`POST /interests/add`、`POST /interests/remove` — 興趣（US3）
- **行為**：list/add/remove 走 `InterestService`；POST 後 302 重導 `/interests`。
- **契約測試**：add 後 `/interests` 顯示新主題；remove 後移除（FR-006）。

## 錯誤邊界（FR-009／原則 V）
- 任一路由的後端呼叫拋 `OpenAIError`（或逾時）→ **例外處理器**回**友善繁中錯誤頁**
  （HTTP 200 或 503 皆可，但**內容為人話、非未處理堆疊**）。
- **契約測試**：注入會拋 `OpenAIError` 的後端 → 回應為友善繁中頁、**不含 Python traceback**、
  無未處理 500。

## 全域
- 靜態：Tailwind 走 CDN（無需 static 路由）；如需少量自訂 CSS 再加 `/static`。
- 所有頁面繼承 `base.html`（RWD viewport、Tailwind、繁中）。
