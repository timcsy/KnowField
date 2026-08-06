# Quickstart: 對話暫時存檔＋TTL 衰減

## 前置
- 在 `028-temporary-save`；`uv run pytest -q` 現 441 綠。
- conversations 加 `temporary`＋`last_activity_at`（冪等 migrate、回填既有=永久）。`knowfield.db` 已備份。

## 跑測試（TDD）
```bash
uv run pytest tests/unit/test_capture_core.py tests/unit/test_temp_save_web.py -q
uv run pytest -q     # 全套不回歸（441 →）
```

## 手動驗證（web，真實 knowfield.db）
```bash
KNOWFIELD_DB=knowfield.db uv run uvicorn knowfield.web.app:create_app --factory --port 8000
```
1. **自動暫存**：`/chat` 聊幾輪 → `/conversations` 的「暫存（會自動清除）」區出現**一筆**（不是每句一筆），便宜標題。
2. **接回**：重整/關掉 `/chat` 再開 → 出現「上次還沒存的對話還在，接回嗎？」→ 接回續聊，仍是同一筆。
3. **升永久**：對某筆暫存按「轉永久」（或聊天頁「存這段對話」）→ 移到「永久」區、標題重生為**落點標題**、不再有 7 天大限。
4. **衰減（可用 SQL 造舊時間驗）**：把某筆暫存的 `last_activity_at` 改成 8 天前 → 重載 `/conversations` → 該暫存消失；永久那些都還在。
5. **不污染**：暫存裡就算有發想，新 `/chat` 也不會把它當場脈絡（守衛測已釘）。

## 驗收對照（spec SC）
- SC-001：每輪自動存一筆（upsert）、可接回、失敗不擋、空不存。
- SC-002：閒置 >7 天清、7 天內碰過不清、純函式、懶清不開背景。
- SC-003：只刪過期暫存、永久零誤刪。
- SC-004：升永久同一筆＋落點標題、不重複；冊封連同存=永久。
- SC-005：暫存不注入回場（守衛）、升永久人閘門。
- SC-006：分區、既有=永久、全繁中、核心零相依、441 不回歸＋新測。
