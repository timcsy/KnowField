# Quickstart：驗證 種子 ingest（增量 2a）

前置：可 `uv run`；`.env` 設好真實後端（或用離線後端跑流程）。

## 1. 收一篇 arXiv 經典進 KB
```bash
uv run learnnews ingest 1706.03762 --explainer     # Attention Is All You Need，標為解說文
uv run learnnews ingest https://arxiv.org/abs/2407.12345   # 用 URL 也可
```
預期：印「✅ 已收進知識庫：<標題>（解說文）」＋原文連結。

## 2. 收一篇解說文（一般 URL）
```bash
uv run learnnews ingest https://某研究者部落格/attention-explained --explainer
```

## 3. 問到它（沿用增量 1，CLI＋web）
```bash
uv run learnnews ask "transformer 為什麼用 attention"
# 或瀏覽器 /ask
```
預期：答案檢索到剛收的種子、列為來源、附原文連結。

## 4. 去重
```bash
uv run learnnews ingest 1706.03762          # 再收一次同篇
```
預期：印「已在庫：<標題>」，KB 不新增第二份。

## 5. 誠實邊界
```bash
uv run learnnews ingest https://不存在的網址.example/x
```
預期：友善繁中錯誤訊息、退出碼 1、**KB 未寫入半殘種子**。

## 6. 測試（TDD 驗收）
```bash
uv run pytest tests/contract/test_ingest.py \
              tests/integration/test_seed_retrieval.py \
              tests/unit/test_seed_fetch.py -q
uv run pytest -q          # 全套：新測綠燈 + 既有 147 不回歸
```

## 驗收對映
| 檢查 | 對映 |
|---|---|
| ingest 單篇進 KB、ask 檢索得到＋溯源 | FR-001/002/003、SC-001、US1 |
| 同篇重複不重複 | FR-004/007、SC-002、US1 |
| 解說文權重＞快訊 | FR-005、SC-003、US2 |
| 抓取失敗友善繁中、不半殘 | FR-006、SC-004、US3 |
| 離線可測、147 不回歸 | FR-009、SC-005 |
| 使用者手動冊封 | FR-008 |
