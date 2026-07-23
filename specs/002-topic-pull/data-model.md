# Phase 1 資料模型：主題拉取深挖（拉模式）

拉模式大量**複用**階段 2 的實體（`specs/001-daily-triage-digest/data-model.md`）：
`Source`、`Item`、`EventCluster`、`Summary` 直接沿用。此處只列拉**新增/特有**的。

## 新增/特有實體

### TopicQuery（主題查詢）
使用者發起拉取的輸入（transient，MVP 不落庫）。
- `topic`：主題字串（如 "latent reasoning"）
- `limit`：結果上限（預設 30，SC-004）
- `with_summary`：是否附一句定位（預設 True；`--raw` 時 False）

### PullResult（拉取結果集）
某次拉取的產出（transient）。
- `topic`：對應的主題
- `entries`：有序清單，元素 = { `item`（複用 Item）, `rank`, `relevance_score`,
  `summary`（複用 Summary，可為 None）}
- `truncated_count`：因上限未納入的則數（不靜默截斷，原則 V）
- `missing_sources`：拉取時不可取得的來源標示（FR-008）
- `is_empty`：無相關結果時為真（Edge Case：冷門主題）

**規則**：
- `entries` 依 `relevance_score`（對**主題**，非興趣清單）排序；長度 ≤ `limit`，
  超出計入 `truncated_count`。
- 每個 entry 的 `item` MUST `has_source_link()`（FR-005）；無原文者排除。
- `with_summary=False` 時所有 `summary` 為 None、且**不呼叫 LLM**（SC-007）。
- 任一 entry 的 summary（若有）長度 ≤ 一句、不含結論式分析（FR-006/006a）。

## 複用實體（不重複定義，見階段 2）
- **Source**：拉取時，可查詢來源（arXiv）以主題查詢 URL 建構；其餘用既有 feed。
- **Item / EventCluster**：擴展得到的材料與去重單位，與推模式相同。
- **Summary**：預設模式的一句定位，與推模式同一封頂守衛。

## 資料流（文字）

```
TopicQuery(topic)
  → 對可查詢來源：建主題查詢 URL → fetch
  → 對其他來源：fetch 近期 → 依主題相關性過濾
  → 合併 → 去重（EventCluster）→ 依主題排序 → 取 limit
  → with_summary? 對進榜者產一句定位 : 略過
  → PullResult
```
