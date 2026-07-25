# Contract：趨勢讀數

## `trend_keywords(titles, top_n=8, stopwords=None, min_count=2) -> list[str]`（`trend/keywords.py`）
- **MUST** 純函式：無 IO、無 API、確定性、離線可測。
- **MUST** 斷詞＝英文詞（len≥2）＋中文相鄰 bigram；跨標題計數。
- **MUST** 過濾內建停用詞∪傳入 `stopwords`；只留 `count ≥ min_count`。
- **MUST** 依 count 降序取前 `top_n`，同分保持首次出現順序（stable）。
- 空/過濾後為空 → 回 `[]`。

## `recent_digest_titles(k=3) -> list[str]`（`store/repository.py`）
- 取最近 K 份真實匯整（`date != SEEDS_DATE`）的 `digest_entries.title`。無匯整 → `[]`。

## `GET /`（首頁擴充）
- 取 `recent_digest_titles(config.trend_recent_digests)` → `trend_keywords(..., top_n=config.trend_top_n)`
  → context 加 `chips`。
- `digest.html`：`chips` 非空 → 頂端渲染熱詞區塊（描述性標題「今日高頻」＋每個 chip 連
  `/pull?topic=<urlencode>`）；`chips` 空 → **不渲染**該區塊（FR-005）。
- 面向使用者全繁中；措辭中性（無「爆紅／未來趨勢」）。

## 契約測試（離線、零外部呼叫）
1. `trend_keywords`：高頻詞排前（給重複出現的詞）；`top_n` 裁切；同分保原序。
2. `trend_keywords`：中英混合——英文詞與中文 bigram 都能成熱詞。
3. `trend_keywords`：停用詞（的/model/AI…）與低於 `min_count` 者被濾掉；全被濾 → `[]`。
4. `recent_digest_titles`：只取真實匯整標題、排除種子容器。
5. 首頁：種幾份匯整（標題含重複主題詞）→ `GET /` 頁面含熱詞 chips、chip 連 `/pull?topic=`。
6. 首頁：無匯整（或算不出）→ `GET /` **不含**熱詞區塊、頁面其餘正常、非 500。
