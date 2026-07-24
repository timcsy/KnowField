# Contract：探索（多角度擴展）

## `QueryExpander.expand(query: str) -> list[str]`（`search/expand.py`）
- `StubQueryExpander`：回**確定性、非空**子角度清單（零外部呼叫）。
- `OpenAIQueryExpander`：`_post` chat 拆解 → 逐行解析 → **上限 max_n**；空回應／例外 → 回 `[]`。
- **MUST NOT** 拋到呼叫端（失敗回 `[]`，由 SmartSearch 退回單 query）。

## `SmartSearch.run(query, explore=False) -> SmartResult`（擴充）
- `explore=False`（預設）：**行為與 spec 010 完全一致**（單 query）。
- `explore=True` 且有 `expander`：
  - **MUST** `angles = dedup([query] + expander.expand(query))[:max_subqueries]`——原 query 必納、上限。
  - **MUST** 對每個 angle 搜尋、依 url 正規化**合併去重**（保留最先出現）。
  - **MUST** 對合併池跑既有 rank/fetch/整理，回 `SmartResult`。
  - expander.expand 拋錯 → **MUST** 退回 `angles=[query]`（等同單 query，教訓 3）。
- 搜尋後端 `SourceUnavailable` **向外拋**（路由攔，同增量 b）。

## `make_query_expander(config)`（`backends/factory.py`）
- openai＋key → `OpenAIQueryExpander`，否則 `StubQueryExpander`。

## `GET /search?q=<q>&explore=<1|空>`（擴充）
- 無 `explore` → 單 query（增量 b）。`explore=1` → 多角度。
- **MUST** 呼叫 `smart_search_factory(q, explore)`；`smart_search_factory` 簽名 `(q, explore=False)`。
- 頁面 **MUST** 有「深入探索」checkbox（`name=explore`），勾選狀態回填。
- 其餘（整理／結果／收進／失敗攔截）同增量 b。

## 契約測試（離線、零外部呼叫）
1. `StubQueryExpander.expand("X")` 回非空、確定性清單。
2. `OpenAIQueryExpander` 用注入 poster 回多行 → 解析成清單、**上限裁切**；空/例外 → `[]`。
3. `SmartSearch.run(q, explore=True)`（注入 StubExpander＋多 web_search 結果含**重複 url**）→
   合併池**去重**（重複 url 只一則）、原 query 納入、`len(angles)≤max`。
4. `run(q, explore=True)` 當 expander 拋錯 → 退回單 query（結果＝單搜尋）、不拋。
5. `run(q, explore=False)` → 只搜一次（等同增量 b；可用計數 web_search 呼叫次數驗）。
6. `/search?q=X&explore=1`（注入 smart_search_factory 驗收到 explore=True）→ 頁面正常、有開關。
7. `/search?q=X`（不帶 explore）→ smart_search_factory 收到 explore=False。
8. 頁面含「深入探索」checkbox；勾選後回填 checked。
