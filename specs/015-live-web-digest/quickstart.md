# Quickstart：live web 活水（階段 13）

前置：`.env` 設了搜尋金鑰（`KNOWFIELD_SEARCH_API_URL`＋`KNOWFIELD_SEARCH_KEY`，同 `/search`）。

## 1. 啟用開放網路趨勢源
```
開 /sources → 找「開放網路 AI 趨勢（需搜尋金鑰・opt-in）」→ 啟用
```
預期：預設是**停用**的；啟用後才會在 digest 時搜開放網路。

## 2. 重新整理 → 匯整含剛紅新聞
```
回首頁按「🔄 重新整理」（或 uv run knowfield digest）
```
預期：匯整**納入開放網路剛紅的 AI 新聞**（Opus 5 這類進得來），每則帶原文連結、經興趣排序、
消化成散文——固定名冊看不到的東西補進來了。

## 3. 進的是流，不是種子
- web 帶進的新聞是**當日流**；看到有價值的那則，按「收進」才冊封成種子（不自動落庫）。

## 4. 不啟用＝零成本
- 不啟用該源（或沒設金鑰）：digest 完全不搜開放網路、行為與現在一致。

## 5. 失敗不擋
- 搜尋服務掛：匯整照常用其他來源產出、標示該源缺漏，不崩。

## 6. 離線可測
```
uv run pytest tests/unit/test_websearch_adapter.py tests/contract/test_live_web_digest.py -q
```
預期：全綠、零外部呼叫（注入 StubWebSearch）。全套 `uv run pytest` 不回歸（≥249）。

## 驗收對照
| 成功標準 | 驗法 |
|---|---|
| SC-001 匯整納入剛紅新聞、可回溯 | 步驟 1+2＋contract 6 |
| SC-002 預設停用、零成本 | 步驟 4＋contract 3/5 |
| SC-003 流非種子、興趣過濾 | 步驟 3＋contract 6 |
| SC-004 失敗照常＋缺漏 | 步驟 5＋contract 7 |
| SC-005 離線可測、零 schema、不回歸 | 步驟 6 |
| SC-006 無自動種子/竄升/成核/LLM擴展/串流 | 程式碼檢視 |
