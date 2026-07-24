# Quickstart：探索（多角度擴展，階段 9 增量 c）

前置：已完成增量 b（`/search` 有整理＋排序）。

## 1. 開深入探索
```
開 http://127.0.0.1:8000/search → 輸入「latent reasoning」→ 勾「深入探索」→ 送出
```
預期：
- 工具從**多個角度**搜（原題＋原理／應用／比較…），結果**合併去重**成一份整理＋清單。
- 涵蓋面比不勾時廣；同一篇文章只出現一次。

## 2. 不勾＝增量 b（不多花成本）
```
同一 query 不勾「深入探索」→ 送出
```
預期：只搜一次、行為與增量 b 完全一致（不觸發拆角度與多次搜尋）。

## 3. 拆角度失敗仍可用
- 拆角度服務失敗／逾時：**自動退回單一 query** 搜尋、照常整理，頁面不崩。

## 4. 離線可測
```
uv run pytest tests/unit/test_expand.py tests/unit/test_smart_search.py \
  tests/contract/test_explore.py -q
```
預期：全綠、零外部呼叫（stub expander＋stub 全鏈）。全套 `uv run pytest` 不回歸（≥209）。

## 驗收對照
| 成功標準 | 驗法 |
|---|---|
| SC-001 多角度＋合併去重 | 步驟 1 |
| SC-002 不勾＝增量 b、不多花 | 步驟 2（web_search 只呼叫一次） |
| SC-003 拆角度失敗退回單 query | 步驟 3 |
| SC-004 子角度≤5、抓取不放大 | contract 3（上限）＋抓取沿用 top-N |
| SC-005 離線可測、不回歸 | 步驟 4 |
| SC-006 agentic 未出現 | 程式碼無多輪迴圈 |
