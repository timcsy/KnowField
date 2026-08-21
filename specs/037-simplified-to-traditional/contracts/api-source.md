# 介面契約：來源詳情頁讀取

## `GET /api/source`

既有端點，**新增一個查詢參數**，其餘回應結構不變。

### 請求

| 參數 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `u` | string | （必填） | 來源 URL，既有參數 |
| `raw` | int | `0` | **新增**。`1` = 回傳未經轉換的原文（FR-005、憲章 VI 的可覆寫出口） |

### 回應

結構與既有完全相同。差別只在 `markdown` 欄位的內容：

| `raw` | `markdown` 內容 |
|---|---|
| `0`（預設） | 簡體已轉為繁體（含詞彙在地化），承重片段逐字不變 |
| `1` | 與儲存內容逐字相同 |

**新增欄位**（供前端決定要不要顯示切換）：

| 欄位 | 型別 | 說明 |
|---|---|---|
| `s2t_applied` | bool | 本次回應是否實際套用了轉換。引擎不可用、`raw=1`、或內容非簡體導致轉換後無變化時皆為 `false` |

### 契約條件

- **C-001**：`raw=1` 的 `markdown` MUST 與 `get_source_chunks` 拼回結果逐字相同。
- **C-002**：對同一 `u`，重複呼叫 MUST 得到相同結果（確定性）。
- **C-003**：轉換引擎不可用時 MUST 回 200 且 `markdown` 為原文、`s2t_applied=false`；MUST NOT 回 5xx。
- **C-004**：`raw` 為非法值（非 0/1、非數字）時 MUST 視為 `0`，MUST NOT 回錯誤。
- **C-005**：既有欄位（`found`、`title`、`original_url`、`pdf_path`、`paper`、`note`、`ingested_at`）
  的語義與型別 MUST 不變（零回歸）。

## 內部契約：`knowfield.text`

```
protect.mask(text) -> (masked: str, segments: list[str])
protect.restore(masked, segments) -> str
    不變式：restore(*mask(t)) == t

s2t.convert(text) -> str
    不變式：
      - 引擎不可用 → 回傳 text 本身（identity）
      - 對已是繁體／英文的輸入 → 回傳逐字相同
      - 確定性：同輸入同輸出
      - 承重片段逐字不變（內部已套用 mask/restore）
```
