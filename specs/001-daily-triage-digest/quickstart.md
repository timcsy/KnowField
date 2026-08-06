# Quickstart：每日推播分診（推模式 MVP）

證明本功能端到端可用的驗證指南。實作細節見 [data-model.md](./data-model.md)、
[contracts/](./contracts/)；本檔只描述如何跑起來與預期結果。

## 前置

- Python 3.12+
- 安裝相依（實作時以 `pyproject.toml` 定義）：`pip install -e .`
- 設定 Anthropic API 金鑰（摘要用）：`export ANTHROPIC_API_KEY=...`
- 首次初始化資料庫與預設來源：`knowfield sources list`（自動建立 SQLite）

## 驗證情境

### 情境 A — 設定興趣並產出匯整（US1＋US2）
```bash
knowfield interests set "LLM 推理" "agent" "編譯器"
knowfield interests list          # 預期：列出三個明講主題
knowfield digest --date 2026-07-23 --limit 15
```
**預期**：輸出一份 ≤15 則、依相關性排序的匯整；每則含「一句定位／一句為何值得看／
直達原文連結」；結尾標示缺漏來源與未納入則數。

### 情境 B — 跨源去重（FR-002／SC-002）
以含「同一論文出現在 arXiv 與 HF Papers」的錄製樣本執行 `digest`。
**預期**：該論文在匯整中**只出現一次**。

### 情境 C — 溯源硬需求（FR-006／SC-003）
檢查情境 A 輸出。
**預期**：**每一則**都有可點擊、直達原文的連結；無連結的條目不出現在匯整中。

### 情境 D — 摘要封頂與不代勞（FR-004/005／SC-004）
檢查任一則摘要。
**預期**：不超過兩句；為「值不值得深挖」的定位，**不含**系統的結論式判斷或深度分析。

### 情境 E — 使用者主權（FR-009／憲章原則 VI）
```bash
knowfield interests remove "編譯器"
knowfield digest --date 2026-07-23
```
**預期**：即使行為訊號曾偏好「編譯器」，移除後該主題不再主導；明講設定優先。

### 情境 F — 來源缺漏不靜默（FR-011／原則 V）
停用或注入某來源失敗後執行 `digest`。
**預期**：匯整照常產出，並在 `missing_sources` 明確標示該來源缺漏；退出碼仍為 0。

### 情境 G — 空匯整（Edge Case）
以「當日無符合興趣條目」的樣本執行。
**預期**：退出碼 0，明確標示為空匯整，不報錯、不硬塞不相關內容。

## 對應的自動化測試（TDD）
- contract：`tests/contract/`（CLI 指令、adapter 介面）
- integration：`tests/integration/`（樣本 → 去重 → 排序 → 摘要 → 匯整，情境 A–G）
- unit：`tests/unit/`（去重、排序、摘要守衛等）

以上情境在實作前先寫成**失敗測試**（憲章原則 I：先紅後綠）。摘要與來源測試以錄製回應／
樣本進行，不打真實 API（確定性）。
