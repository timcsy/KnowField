# Quickstart：驗證 RAG 問答 MVP

前置：已能 `uv run` 專案；已跑過至少一次 `digest`（庫裡有匯整條目）。

## 1. 離線問答（零外部呼叫，預設 stub 後端）
```bash
# 未設 api_key → 自動離線後端
uv run learnnews digest            # 先產生一份匯整（若還沒有）
uv run learnnews ask "最近有什麼值得看的"
```
預期：印出一段繁中答案＋「來源：」清單（每則附原文連結）；或在庫空/無關時印「沒有相關材料」。

## 2. 範圍過濾
```bash
uv run learnnews ask "今天的重點" --today     # 只查最近一份匯整
uv run learnnews ask "agent 記憶體進展"         # 預設跨全部累積匯整
```
預期：`--today` 的來源只含最近一份匯整的條目。

## 3. 真實後端（品質＋忠實抽查）
```bash
# .env 設 LEARNNEWS_API_KEY（勿貼進聊天/勿進版控）
uv run learnnews ask "最近 RL 有什麼新方向"
```
預期：答案更通順、逐點 `[n]` 標來源；**人工抽查**：每個論點都能在對應來源原文找到依據
（無杜撰）。

## 4. 誠實邊界
```bash
uv run learnnews ask "完全無關的冷門主題xyz"    # → 沒有相關材料，不硬答
```

## 5. 測試（TDD 驗收）
```bash
uv run pytest tests/contract/test_ask.py tests/integration/test_rag_service.py \
              tests/unit/test_entry_embeddings.py -q
uv run pytest -q          # 全套：新測綠燈 + 既有 128 不回歸
```

## 驗收對映
| 檢查 | 對映 |
|---|---|
| 答案掛來源、可回原文 | FR-003、SC-001、US1 |
| `--today` vs 累積正確 | FR-005、SC-003、US2 |
| 查無說無不杜撰 | FR-004、SC-002、US3 |
| 後端失敗友善繁中、無堆疊 | FR-006、SC-005、US3 |
| 離線零呼叫綠燈、128 不回歸 | FR-008、SC-006 |
| 批次嵌入落庫、查詢 O(1) 呼叫 | FR-009、SC-004 |
| 舊條目不被漏掉 | FR-010 |
