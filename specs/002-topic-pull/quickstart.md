# Quickstart：主題拉取深挖（拉模式）

證明拉模式端到端可用。實作細節見 [data-model.md](./data-model.md)、[contracts/](./contracts/)。
沿用階段 2 的環境（見 `docs/usage.md`）。

## 前置
- 已安裝專案：`uv sync --extra dev`
- （可選）真實後端：填 `.env`（見階段 2 quickstart）；否則用離線 stub。

## 驗證情境

### 情境 A — 對主題拉取（US1，預設附定位）
```bash
uv run knowfield pull "latent reasoning" --limit 20
```
**預期**：一份依「latent reasoning」相關性排序、去重、每則含一句定位＋直達原文的清單；
結尾標示缺漏來源與未納入則數。

### 情境 B — 純原礦模式（SC-007）
```bash
uv run knowfield pull "latent reasoning" --raw
```
**預期**：每則僅標題＋來源＋連結，**完全無生成文字**；且未呼叫 LLM。

### 情境 C — 跨源去重（FR-003／SC-003）
以含「同一論文出現在 arXiv 與 HF」的樣本拉取。
**預期**：該論文只出現一次。

### 情境 D — 溯源硬需求（FR-005／SC-002）
檢查情境 A 輸出。
**預期**：每則都有可點、直達原文的連結；無原文者不出現。

### 情境 E — 不代勞（FR-006／SC-005）
檢查任一則。
**預期**：不含系統對主題的結論、評價或深度分析（預設模式的定位也僅為決策輔助）。

### 情境 F — 來源缺漏不靜默（FR-008）
注入某來源失敗後拉取。
**預期**：照常回傳其餘來源結果，`missing_sources` 標示缺漏，退出碼 0。

### 情境 G — 冷門主題空結果（Edge Case）
```bash
uv run knowfield pull "某個查無相關的冷門詞"
```
**預期**：退出碼 0，明確標示無相關結果，不報錯、不硬塞。

## 對應自動化測試（TDD）
- contract：`tests/contract/test_cli_pull.py`、`test_topic_query.py`
- integration：`tests/integration/test_pull_*.py`（情境 A–G）
- unit：`tests/unit/test_pull_service.py`

情境先寫成**失敗測試**（原則 I）。來源／摘要以樣本、stub 進行，不打真實 API。
