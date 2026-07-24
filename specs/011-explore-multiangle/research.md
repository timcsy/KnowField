# Research：探索（多角度擴展，階段 9 增量 c）

## R1：QueryExpander 介面與放置
- **決策**：新模組 `search/expand.py`，`QueryExpander` Protocol `expand(query)->list[str]`；
  `StubQueryExpander`（離線確定性）＋`OpenAIQueryExpander`（真實）。與 websearch/smart 同層。
- **理由**：拆角度是獨立、可插拔的一步；與 WebSearch/SmartSearch 同層、依賴注入 → 離線可測（教訓 1）。

## R2：離線 stub 怎麼回子角度（可測、確定性）
- **決策**：`StubQueryExpander.expand(q)` 回 `[f"{q} 原理", f"{q} 應用", f"{q} 比較"]`（確定性、
  貼題、不含原 q——原 q 由 `_collect` 保證納入）。契約測試據此驗 fan-out＋去重、零外部呼叫。
- **理由**：確定性讓契約測試可斷言合併/去重行為；離線也能展示多角度形狀。

## R3：OpenAIQueryExpander 拆解（複用 _post）
- **決策**：`_post(base,"/chat/completions",key,{model,messages})` 送 system＝「把使用者問題拆成
  N 個**不同角度、貼題**的子查詢，每行一個，只輸出子查詢、勿編號勿解說」；解析回應**逐行**
  取非空行、去掉可能的序號/符號、上限 `max_subqueries`。空回應／例外 → 回 `[]`（由呼叫端退回單 q）。
- **理由**：complete 複用既有 chat 後端、零新相依（憲章 IV）。防跑題靠 prompt「貼題」＋整理層
  仍 grounded（跑題子查詢撈到的無關結果，排序低、整理不引用）。

## R4：SmartSearch 接 expander（explore 參數）
- **決策**：`SmartSearch(__init__ 加 expander=None)`；`run(query, explore=False)`。新增 `_collect`：
  ```
  if explore and expander:
      subs = try expander.expand(query) except → []      # 教訓 3：拆解失敗退回
      angles = dedup([query] + subs)[:max_subqueries]     # 原 query 一定納入、上限
      merged = []; seen=set()
      for a in angles:
          for r in web_search.search(a):                  # 搜尋層失敗 → 向外拋（同增量 b）
              if norm(r.url) not in seen: seen.add(...); merged.append(r)
      return merged
  else: return list(web_search.search(query))             # 增量 b 單 query
  ```
  之後 rank/fetch/整理**完全沿用**（run 其餘不變）。
- **理由**：fan-out 只影響「結果從哪來」；整理管線一行不改（復用最大化）。原 query 永遠在
  angles → explore 不會比單 query 差。

## R5：合併去重
- **決策**：依 url **正規化**（去尾斜線、去 `#fragment`；query string 保留）比對，保留**最先出現者**。
- **理由**：同文章跨角度重複只留一則，整理不吃重複材料（FR-003）；正規化避免尾斜線假重複。

## R6：成本雙閘（根公理）
- **決策**：① opt-in 預設關（不勾＝零探索成本）；② 子角度 `≤ max_subqueries`（預設 5，config 可調）；
  ③ **抓取內文仍受 SmartSearch top-N 限制**——合併池再大，只 fetch top-N。
- **理由**：搜尋是便宜的一步（且多角度是價值來源），貴的是**抓網頁＋LLM 整理**；把抓取閘在
  top-N＝多角度變廣但成本不爆。單輪、可預測。

## R7：/search 開關與路由
- **決策**：`search.html` 搜尋表單加 `<input type=checkbox name="explore" value="1">`（沿用 ask.html
  的 today 勾選樣式），勾選狀態回填。路由 `search_get(q, explore="")`→`bool(explore)`→
  `smart_search_factory(q, explore)`。`smart_search_factory` 簽名改 `(q, explore=False)`。
- **理由**：最小 UI；explore 預設關（value 未送＝False）。既有注入點測試同步改 `(q, explore=False)`。

## R8：失敗與邊界
- 拆解失敗／逾時 → `[]` → angles=`[query]` → 等同單 query（FR-007，教訓 3）。
- 子角度只回 1 或全與原 q 重複 → dedup 後可能只剩 `[query]`，正常。
- 搜尋後端整體失敗（SourceUnavailable）→ 向外拋、路由攔成「搜尋失敗」（同增量 b/9）。
