# Quickstart: 既有重複對話清理

## 前置
- 在 `026-dedupe-conversations`；`uv run pytest -q` 現 414 綠。
- 無結構變更（只刪多餘列＋UPDATE 連結）。`learnnews.db` 已備份（`learnnews.db.bak-*`）。

## 跑測試（TDD）
```bash
uv run pytest tests/unit/test_capture_core.py tests/unit/test_dedupe_web.py -q
uv run pytest -q     # 全套不回歸（414 →）
```

## 手動驗證（web，真實 learnnews.db）
```bash
LEARNNEWS_DB=learnnews.db uv run uvicorn learnnews.web.app:create_app --factory --port 8000
```
1. `/conversations` → 按「🧹 清理重複對話」→ 預覽頁應顯示：發現 N 組（含那 15 份 Flow Matching 那組）、共 M 份多餘、K 條根因將重指。**此時資料未變**（可先回 `/conversations` 確認份數不變）。
2. 按「確認清理」→ 回 `/conversations`，看清單**大幅變短**（15 份→1 份等）；成功 flash「已清理：併掉 M 份、重指 K 條根因」。
3. `/roots` → 每條原本有「← 由來」的根因**仍連得到**（都指向留存那份）。
4. 隨機開一條根因 → 主張／階梯**未變**（清理只動由來連結與多餘份）。
5. `/conversations` 檢查 #18/#19（65/70 句版）等**內容不同者仍在**（沒被誤併）。

## 驗收對照（spec SC）
- SC-001：預覽正確、執行前資料零變動。
- SC-002/003：同組留 1（最新）、根因全重指、清理後「← 由來」不斷。
- SC-004：異指紋份數不變、根因主張未改。
- SC-005：`plan_dedupe` 純函式測綠、空/無重複友善。
- SC-006：人確認才執行；全繁中；核心零相依；414 不回歸＋新測。
```
