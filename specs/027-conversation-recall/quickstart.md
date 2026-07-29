# Quickstart: 對話的可找回性

## 前置
- 在 `027-conversation-recall`；`uv run pytest -q` 現 423 綠。
- 無結構變更（US1 只 UPDATE title；章節不落庫）。

## 跑測試（TDD）
```bash
uv run pytest tests/unit/test_capture_core.py tests/unit/test_recall_web.py -q
uv run pytest -q     # 全套不回歸（423 →）
```

## 手動驗證（web，真實 learnnews.db）
```bash
LEARNNEWS_DB=learnnews.db uv run uvicorn learnnews.web.app:create_app --factory --port 8000
```
1. **US1 重生標題**：`/conversations` 開一則叫「Flow Matching…」的長對話 → 按「重新命名」→ 標題應重生成反映**落點**（四元樹/影片串流），不再只是開頭。也可直接**改名**輸入自己的。
2. **US1 新標題**：`/chat` 聊一段「開頭 A、落點 B」→ 存 → 標題反映 B。
3. **US2 章節**：開一段長對話 →「整理成章節」→ 出章節大綱（小標＋第 N–M 句＋摘要）；點某章**跳到**該段。
4. **US3 每章**：某章按「複製 Markdown」→ 只含該章；按「整理這章成重點」→ 出候選、由你決定冊封（不自動）。
5. 短對話 / 後端失敗 → 友善退回（標題退首句、切分退整段一章），不崩。

## 驗收對照（spec SC）
- SC-001/002：標題反映落點、可手動改名、既有可重生；可注入、失敗退回、不自動改。
- SC-003/004：切出小標＋範圍＋摘要、可跳讀、涵蓋不重疊；可注入、退回、不落庫。
- SC-005：每章可單獨匯出／整理（人閘門、不自動冊封）。
- SC-006：全繁中、核心零相依、423 不回歸＋新測。
```
