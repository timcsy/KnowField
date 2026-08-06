# Quickstart：驗證 知識庫管理（階段 7）

前置：可 `uv run`；已 ingest 幾則種子（`knowfield ingest …` 或 web 收進）。

## 1. 瀏覽
```bash
uv run uvicorn knowfield.web.app:app     # 開 http://127.0.0.1:8000/library
```
預期：看到你收的種子（標題/類型/日期/原文連結）；每日匯整條目**不**出現。

## 2. 刪除
在 /library 按某則「刪除」→ 該則消失。回「問答」問它 → 應**檢索不到**了。

## 3. 重分類
把一則「一般」改「解說文」→ 對相關問題問 `ask`，它的檢索權重提高（解說文加權）。

## 4. 空狀態
清空所有種子 → /library 顯示空狀態提示。

## 5. 每日流保護
確認 /library 沒有任何刪除每日匯整條目的入口。

## 6. 測試（TDD 驗收）
```bash
uv run pytest tests/unit/test_seed_management.py tests/contract/test_web_library.py -q
uv run pytest -q      # 全套：新測綠燈 + 既有 166 不回歸
```

## 驗收對映
| 檢查 | 對映 |
|---|---|
| 列種子、不含每日流 | FR-001/005、SC-001、US1/US3 |
| 刪除+清嵌入、ask 檢索不到 | FR-002/003、SC-002、US1 |
| 重分類權重跟上 | FR-004、SC-003、US2 |
| 每日流不可刪 | FR-005、SC-004、US3 |
| 空狀態、全繁中 | FR-006/007、SC-005 |
| 離線可測、166 不回歸 | FR-008、SC-006 |
