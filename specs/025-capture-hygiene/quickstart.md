# Quickstart: 對話收料的漏

## 前置
- 在 `025-capture-hygiene`；`uv run pytest -q` 現 393 綠。
- 加一欄 `why_nodes.conversation_id`（冪等 migrate、回填既有）；不新增表。

## 跑測試（TDD）
```bash
uv run pytest tests/unit/test_capture_core.py tests/unit/test_capture_hygiene_web.py -q
uv run pytest -q     # 全套不回歸（393 →）
```

## 手動驗證（web）
```bash
LEARNNEWS_DB=learnnews.db uv run uvicorn learnnews.web.app:create_app --factory --port 8000
```
1. **#1 去重**：`/chat` 聊幾句 → 「整理成重點」→ 對多條候選各勾「連同這段對話存成由來」逐條「存這條」→
   到 `/conversations`：這段對話**只出現一次**；到 `/roots`：那幾條根因的「← 由來」**都指向同一段**。
2. **異段不誤併**：換一段內容不同的對話重複上步 → `/conversations` 多出**另一份**（非併入）。
3. **#2 提醒**：在 `/chat` 聊得夠長、且一陣子沒整理 → 頁面出現「尾段未收，約第 N–M 句，要不要現在整理？」；
   短對話或剛整理過 → **不出現**。點提醒 → 走既有「整理成重點」；忽略 → 什麼都不會被自動存。

## 驗收對照（spec SC）
- SC-001/002：同段 N 冊封只增 1 份、N 連同一；異段不誤併；單獨冊封不增。
- SC-003：長且未收→提醒＋區間；短/剛收→無。
- SC-004：`distill_gap`／`fingerprint` 純函式測綠；提醒不自動冊封（守衛測）。
- SC-005：去重不刪改既有；`_migrate` 冪等、既有 spec 023 存檔仍可讀（既有 provenance 回填不斷）。
- SC-006：全繁中、核心零相依、393 不回歸＋新測。

## 注意（範圍外）
- 既有 15 份歷史複本**本輪不清理**（只保證以後不再複製）；#3 標題/章節切分不做。
