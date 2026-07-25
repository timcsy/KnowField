# Research：趨勢讀數（階段 11）

## R1：斷詞策略（中英混合）
- **決策**：自寫輕量斷詞——**英文**取 `[A-Za-z0-9][A-Za-z0-9+\-.]*`（len≥2、小寫）；**中文**取
  **相鄰 CJK 雙字（bigram）**（`推理`、`記憶`…）。合成候選詞集合計數。
- **理由**：既有 `tokenize`（`ranking/embeddings.py`）把中文拆成**單字**（`[一-鿿]` 逐字），單字
  不成主題詞。bigram 是零相依、夠用的中文主題抓法（不引入分詞相依，YAGNI）。英文詞直接用。
- **否決**：引入 jieba 等中文分詞 → 加相依，違憲章 IV；只用單字 → 熱詞無意義。

## R2：計數與門檻
- **決策**：跨所有標題計每個候選詞**出現次數**；過濾停用詞後，保留 **count ≥ min_count（預設 2）**
  者，依 count 由高到低取 top_n（預設 8）。同分保持首次出現順序（stable）。
- **理由**：出現≥2 才算「趨勢」而非一次性；門檻讓稀疏材料時**自然算不出→ chips 省略**（FR-005）。

## R3：停用詞
- **決策**：內建小型停用詞集——**英文常見**（the/a/of/for/to/and/with/new/using/via/on/in…）＋
  **中文常見**（的/了/在/是/和/與/一個/如何/我們…）＋**領域泛詞**（模型/方法/研究/系統/model/
  method/paper/learning/AI…）。可由呼叫端覆寫/擴充。
- **理由**：泛詞（模型/AI）幾乎每篇都有、無辨識度（FR-007）。停用詞集內建於 `trend/keywords.py`。

## R4：計算來源（哪些標題）
- **決策**：新 `repository.recent_digest_titles(k=3)`——取最近 **K 份真實匯整**（`date != SEEDS_DATE`，
  排除種子容器）的 `digest_entries.title`。K 預設 3。
- **理由**：近幾份反映「當前」；排除種子（種子是深度吸引子、非流的趨勢）。零 schema 變更（讀既有表）。
- **註**：draft 待解 #2 的「全量候選池」未落庫——本 MVP 用**已落庫 top-N 標題**（窄但零改動），
  全量池落庫留後續。

## R5：純函式＋離線可測
- **決策**：`trend_keywords(titles: list[str], top_n=8, stopwords=None, min_count=2) -> list[str]`
  為**純函式**（無 IO、無 API）。契約測試直接餵標題陣列驗排序/過濾，零外部呼叫（教訓 1）。
- **理由**：把統計與 IO 分離 → 好測、好複用（日後 CLI/其他頁可共用）。

## R6：首頁串接與優雅省略
- **決策**：`home` route 取 `recent_digest_titles(config.trend_recent 或 3)` → `trend_keywords(...,
  top_n=config.trend_top_n)` → 傳 `chips` 給 `digest.html`。`chips` 為空 → 模板**不渲染**該區塊。
- **理由**：FR-005 不擺空殼；成本低（讀既有表＋純統計，非 web 請求打 API）。

## R7：chip 連結與措辭
- **決策**：chip → `/pull?topic=<urlencode(詞)>`（既有深挖）。區塊標題用**描述性中性**字樣，
  如「🔥 今日高頻」，**不用**「即將爆紅／未來趨勢」（原則 4、FR-004）。
- **理由**：熱詞是**對已抓材料的描述性讀數**，點下去是溯源後的真實文章（原則 3）。

## R8：範圍守恆（防蔓延）
- 不做：LLM 萃取（(a)，防幻覺，後續）、竄升排序（需存歷史，後續）、成核（後續）、全量池落庫
  （改匯整落庫，後續）、live web 熱詞（已有 `/search`）、CLI。
