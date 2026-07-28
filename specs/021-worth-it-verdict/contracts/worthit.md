# 契約：反逢迎的「值不值得」副手（spec 021）

## `worthit_queries(subject: str) -> list[str]`（新）
確定性多角度獵心得查詢（**非查通用名**）：心得/評價、review reddit、vs 缺點 complaints、
值得嗎 limitations、怎麼用 how to use。`subject` 空 → `[]`。

## `WorthItSynthesizer.synthesize(subject: str, evidence: list[SearchResult]) -> str`（新）
- **Stub**（離線）：確定性繁中綜合、引用 evidence 的 url、零外部呼叫。
- **OpenAI**：`_post` chat，反逢迎 `_SYSTEM`（官方/獨立/用戶分開、明說炒作/缺點/難搞、**只依 evidence＋
  附引用、某層查無說「沒搜到」、不杜撰**、末給值不值得＋怎麼用）。`poster` 可注入。失敗拋 `OpenAIError`。

## `assess_worth(web_search, synthesizer, subject, *, content=None, result_cap=12) -> WorthItVerdict`（新）
1. `queries = worthit_queries(subject)`。
2. 對每 query `web_search.search(q, news=False)`；蒐集、按 url 去重、取前 `result_cap`。搜尋全失敗→拋 `SourceUnavailable`。
3. 無結果 → `WorthItVerdict(no_material=True, ...)`（不呼叫綜合或綜合誠實說資料太少）。
4. 有證據 → `verdict_md = synthesizer.synthesize(subject, evidence)`；回 `WorthItVerdict`。
- **不落庫**：純函式、短暫產出。

---

# 契約：web 路由（spec 021）

## `GET /worth`（新）
手機友善表單：一個 textarea「貼名字或內文」＋選填 url。

## `POST /worth`（新）
- **輸入**（Form）：`subject`（名字/短文字）、`content`（客戶端內文，牆內）、`url`（選填）——任一可觸發。
- **subject 解析序**：`subject` 明給 ＞ `content` 首非空行（截斷）＞ `url` 可抓到的標題（`fetch_url`
  best-effort、try/except）＞ `url` 本身。三者皆空 → 友善提示「請貼名字或內文」。
- **行為**：`verdict = app.state.worth_factory(subject, content)`；render `worth.html` 加 `verdict`。
  - `no_material` → 頁面顯示「這東西太新/資料太少」。
  - `SourceUnavailable`/`OpenAIError` → `_log.error`＋友善 `err`，頁不崩（教訓 3）。
- **收內容口**：`content` 欄即客戶端內文入口（牆內也送得進來）；伺服器抓 url＝best-effort、被擋不崩。

## `worth.html`（新）＋ `base.html` 導覽
- 綜合呈現：`verdict_md`（分段）＋ `sources` 引用連結清單。RWD、手機友善。
- 導覽加「值不值得」入口。
