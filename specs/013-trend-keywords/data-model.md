# Data Model：趨勢讀數

**不新增資料表、不改既有表**（教訓 8）。全記憶體、讀取即算、不落庫。

## 純函式（`trend/keywords.py`）
`trend_keywords(titles: list[str], top_n: int = 8, stopwords: set[str] | None = None,
min_count: int = 2) -> list[str]`
- 回排序後的熱詞清單（高頻在前、同分保原序）。
- 斷詞：英文詞（len≥2 小寫）＋中文相鄰雙字 bigram。
- 過濾：內建停用詞（英文常見＋中文常見＋領域泛詞）∪ 傳入 `stopwords`；`count ≥ min_count`。
- 內建常數：`STOPWORDS`（set）。

## Repository（讀既有表，不改結構）
`recent_digest_titles(k: int = 3) -> list[str]`
- 取最近 K 份**真實匯整**（`date != SEEDS_DATE`）的 `digest_entries.title`。

## Config
- `trend_top_n: int = 8`（`KNOWFIELD_TREND_TOPN`）。
- `trend_recent_digests: int = 3`（`KNOWFIELD_TREND_RECENT`）。

## 首頁 context 新增
- `chips: list[str]`——熱詞清單（空則模板不渲染區塊）。

## 熱詞 → 深挖
- 每個 chip 連 `/pull?topic=<urlencode(詞)>`（既有 pull）。

## 不變式
- **不落庫**：熱詞每次讀取即算，不寫 DB。
- **可回溯**：熱詞源自真實落庫標題；點擊 → `/pull` 溯源真實材料（原則 3）。
- **中性描述**：措辭「今日高頻」，不預言（原則 4）。
- **優雅省略**：`chips` 空 → 不顯示區塊（FR-005）。
