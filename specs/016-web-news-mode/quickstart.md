# Quickstart：web 活水 news 模式（階段 13 增量 b）

前置：已完成階段 13（web 活水），`web-ai-trends` 已啟用、搜尋金鑰已設。

## 1. web 活水改回近期新聞
```
回首頁按「🔄 重新整理」
```
預期：開放網路帶進的材料是**近期新聞**（預設一週內），SEO 常青清單文（Top 7 LLMs 這種）
明顯減少——撈得到剛紅的產品新聞。

## 2. 手動 /search 不變
```
/search 打一個主題
```
預期：**一般搜尋**（不限新聞、不限時間），涵蓋教學/文件/討論——與現況一致。

## 3. 調時間範圍
```
.env 設 LEARNNEWS_SEARCH_NEWS_RANGE=day → 重啟 → 重新整理
```
預期：web 活水只撈**當日**新聞。

## 4. 離線可測
```
uv run pytest tests/unit/test_websearch.py tests/unit/test_websearch_adapter.py -q
```
預期：全綠、零外部呼叫（poster 驗 payload 帶 topic/time_range）。全套不回歸（≥260）。

## 驗收對照
| 成功標準 | 驗法 |
|---|---|
| SC-001 web 活水回近期新聞 | 步驟 1＋contract 1/4 |
| SC-002 /search 維持一般搜尋 | 步驟 2＋contract 2/6 |
| SC-003 時間範圍可調 | 步驟 3 |
| SC-004 向後相容、離線可測、不回歸 | 步驟 4＋contract 2/3 |
| SC-005 失敗沿用缺漏 | 既有機制不變 |
