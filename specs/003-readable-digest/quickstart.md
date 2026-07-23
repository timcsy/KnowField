# Quickstart：可讀文章式消化

證明散文消化端到端可用。細節見 [data-model.md](./data-model.md)、[contracts/](./contracts/)。
沿用階段 1–4 環境（見 `docs/usage.md`）。

## 前置
- `uv sync --extra dev`
- （可選）真實後端：填 `.env`（散文與 AI 圖走 OpenAI 格式 API）；否則離線 stub。

## 驗證情境

### 情境 A — 每日匯整的散文消化（US1）
```bash
uv run learnnews interests set "LLM 推理"
uv run learnnews digest --format markdown
```
**預期**：每則是一篇可讀散文（非列點），完整傳達重點/數據/適用時機，附一鍵原文連結。

### 情境 B — 主題拉取的散文消化（US1，推拉皆套用）
```bash
uv run learnnews pull "latent reasoning" --format markdown
```
**預期**：同樣是散文文章清單，每則一鍵原文。

### 情境 C — 忠實不捏造（FR-002／SC-002）
以「原文只有標題、無數據」的樣本產生消化。
**預期**：散文不出現原文沒有的數據；寧可不寫。

### 情境 D — 不下工具結論（FR-003／SC-003）
檢查任一散文。
**預期**：內容是傳達原文重點，不含工具自行下的第一性結論或趨勢外推。

### 情境 E — 原文圖（FR-006）
對有原文圖的新聞樣本產生消化（markdown）。
**預期**：文章內嵌原文圖並標為原文。

### 情境 F — AI 示意圖標示（FR-007／SC-005）
```bash
uv run learnnews pull "某無原文圖的主題" --ai-image --format markdown
```
**預期**：無原文圖時附 AI 圖，且**明確標「AI 示意・非原文」**。

### 情境 G — 純原礦（FR-008／SC-006）
```bash
uv run learnnews pull "latent reasoning" --raw
```
**預期**：僅標題＋來源＋連結，無散文無圖，未呼叫生成後端。

### 情境 H — 優雅降級（FR-011／SC-007）
注入散文後端失敗後執行。
**預期**：該則退精簡（標示消化暫不可用）、整體不炸 traceback、退出碼 0。

## 對應自動化測試（TDD）
- contract：`tests/contract/test_cli_article.py`、`test_figure_extract.py`
- integration：`tests/integration/test_article_*.py`（情境 A–H）
- unit：`tests/unit/test_article_builder.py`、`test_ai_image_label.py`

情境先寫成**失敗測試**（原則 I）。散文/AI 圖以 stub、抓圖以錄製樣本，不打真實 API。
真實後端接上後 MUST 抽查散文忠實度（experience 教訓 2）。
