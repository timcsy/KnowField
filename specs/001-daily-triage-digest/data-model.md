# Phase 1 資料模型：每日推播分診（推模式 MVP）

實體對應 spec.md「Key Entities」與 FR。儲存於 SQLite（見 research.md R6）。
所有面向使用者文字為繁中（FR-010）。

## 實體

### Source（來源）
一個可取得條目的出處。
- `id`（主鍵）
- `name`：顯示名稱（繁中）
- `type`：`paper` | `news` | `blog`
- `access_method`：`arxiv_api` | `hf_papers` | `semantic_scholar` | `rss` | `email_ingest`
- `endpoint`：查詢端點／feed URL
- `enabled`：布林
- `last_fetch_at`、`last_status`：可用性狀態（供 FR-011 標示缺漏）

**驗證**：`type` 與 `access_method` 須為列舉值；`endpoint` 非空。

### Item（條目）
一則新聞或論文。
- `id`（主鍵）
- `source_id` → Source
- `external_id`：來源側識別碼（arXiv ID／DOI／guid）
- `title`：原始標題
- `abstract`：摘要／前文（可空）
- `url`：**直達原文連結**（FR-006，硬性；空則不得進匯整）
- `published_at`：發布時間
- `lang`：原文語言
- `cluster_id` → EventCluster（去重後歸屬）
- `fetched_at`
- `content_hash`：正規化標題＋識別碼的雜湊（去重精確層用）

**驗證**：`url` 非空才可進入匯整（FR-006）；`content_hash` 唯一性用於精確去重。

### EventCluster（事件群組）
被判定為「同一則／同一事件」的條目集合，去重單位（FR-002）。
- `id`（主鍵）
- `canonical_item_id` → Item：代表條目（進匯整者）
- `member_item_ids`：成員清單
- `signature`：語義層叢集特徵（實體集合＋embedding 群心參考）

**規則**：一個 EventCluster 在單一 Digest 中僅由 `canonical_item` 代表出現一次（SC-002）。

### InterestProfile（興趣畫像）
使用者的興趣定義（FR-008、FR-009；憲章原則 VI）。
- `id`（主鍵，MVP 單一使用者可固定）
- `explicit_topics`：**明講**主題清單（字串陣列，使用者可檢視/新增/移除/覆寫）
- `learned_weights`：從行為學到的主題權重（可空；US3/FR-012）
- `updated_at`

**規則**：排序時 `explicit_topics` 為 prior；`learned_weights` 疊加但**不得覆蓋使用者的
明講移除**（明講優先）。使用者的任何明講變更即時記錄，次日匯整生效（FR-009、SC-005）。

### Summary（摘要）
附著於進入匯整之條目的封頂文字（FR-004、FR-005、SC-004）。
- `item_id` → Item（一對一，僅匯整條目才生成）
- `positioning`：一句定位（繁中）
- `why_worth`：一句為何值得看（繁中）
- `generated_at`

**驗證（硬守衛）**：`positioning` + `why_worth` 合計 ≤ 兩句；**不得含結論式判斷或深度
分析**（FR-005，由提示＋程式端檢查共同保證）。

### Digest（每日匯整）
某日產出、去重且排序後的條目清單（FR-007）。
- `id`（主鍵）
- `date`：產出日期
- `entries`：有序清單，元素 = { `cluster_id`/`item_id`, `rank`, `relevance_score`, `summary` }
- `truncated_count`：因上限（≤15，SC-007）未納入的則數（可觀測，避免靜默截斷，原則 V）
- `missing_sources`：當日不可取得的來源標示（FR-011）
- `is_empty`：當日無符合條目時為真（Edge Case）

**規則**：`entries` 依 `relevance_score` 排序；長度 ≤ 使用者設定上限（預設 15）；
超出者計入 `truncated_count` 而非默默丟棄。

### BehaviorSignal（行為訊號，US3/FR-012，可後續）
- `id`、`item_id` → Item、`action`：`clicked` | `skipped`、`at`
- 用於 `InterestProfile.learned_weights` 的校準；明講永遠可覆寫。

## 關係圖（文字）

```
Source 1──* Item *──1 EventCluster
Item 1──0..1 Summary
InterestProfile 1──* BehaviorSignal
Digest *──* EventCluster（透過 entries，取 canonical_item）
```

## 狀態轉移（Item 的去重歸屬）

```
新取得 Item
  → 精確層比對 content_hash / external_id
     命中 → 併入既有 EventCluster
     未命中 → 語義層 embedding 相似度比對
        超門檻 → 併入該 EventCluster
        否則 → 建立新 EventCluster（自成 canonical）
```
