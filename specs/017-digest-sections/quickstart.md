# Quickstart：匯整分區（階段 14）

## 1. 首頁分兩區
```
開 http://127.0.0.1:8000/（有近期匯整）
```
預期：頂端熱詞 chips／重整鈕之下，匯整分兩區——
- **📰 今日新聞**：TechCrunch、Verge、Ars、Import AI、HN、Reddit、web 活水…
- **📚 基礎知識精選**：arXiv 論文、ycc 教學、Lilian Weng 經典部落格…
兩區每則都可點回原文。

## 2. 空區不顯示
- 若只啟用新聞源（無基礎源條目）：只顯示「今日新聞」區，不擺空的基礎區。

## 3. 舊匯整不崩
- 本功能前產的舊匯整（條目無來源分類）：照常顯示（落新聞區）、不崩。

## 4. 重新整理後生效
```
按「🔄 重新整理」→ 新匯整帶來源分類 → 首頁正確分兩區
```

## 5. 離線可測
```
uv run pytest tests/unit/test_digest_sections.py tests/contract/test_sections.py -q
```
預期：全綠、零外部呼叫。全套不回歸（≥268）。

## 驗收對照
| 成功標準 | 驗法 |
|---|---|
| SC-001 分兩區、各落對區 | 步驟 1＋contract 3 |
| SC-002 HN/Reddit 歸新聞、可回原文 | contract 6＋步驟 1 |
| SC-003 空區不顯示、舊資料不崩 | 步驟 2/3＋contract 4/5 |
| SC-004 產生流程不變 | 只改呈現＋新增欄 |
| SC-005 最小向後相容、不回歸 | 步驟 5＋contract 1 |
