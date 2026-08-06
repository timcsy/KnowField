# 任務清單：反逢迎的「值不值得 follow」副手（時刻 A）

**規格**：[spec.md](./spec.md) ｜ **計畫**：[plan.md](./plan.md) ｜ **分支**：`021-worth-it-verdict`

TDD 強制：先寫紅測（Red）→ 實作轉綠（Green）。核心零新相依、零新表；串既有可插拔零件。

---

## Phase 1：Setup
（無——沿用既有 web/搜尋/LLM 基礎設施；不新增相依。）

## Phase 2：Foundational（純函式核心，阻塞路由）

- [X] T001 [P] 在 `tests/unit/test_worthit.py` 寫 `worthit_queries` 紅測：給 subject → 回多角度獵心得查詢（含心得/評價、review、缺點/complaints、值得嗎/limitations、怎麼用/how to use 等角度，**非只查通用名**）；空 subject → `[]`。
- [X] T002 [P] 在 `tests/unit/test_worthit.py` 寫 `StubWorthItSynthesizer` 紅測：給 subject＋evidence（假 SearchResult）→ 回繁中綜合、**引用到 evidence 的 url**、零外部呼叫。
- [X] T003 [P] 在 `tests/unit/test_worthit.py` 寫 `assess_worth` 紅測：注入假 web_search（多 query 回重複 url）＋stub synthesizer → ①按 url 去重、②`no_material=True` 當無結果、③search 全失敗拋 `SourceUnavailable`。
- [X] T004 建 `src/knowfield/search/worthit.py`：`worthit_queries(subject)`（確定性模板）＋`@dataclass WorthItVerdict`＋`WorthItSynthesizer` Protocol＋`StubWorthItSynthesizer`＋`assess_worth(web_search, synthesizer, subject, *, content=None, result_cap=12)`。跑 T001/T002/T003 轉綠。
- [X] T005 [P] 在 `tests/unit/test_worthit.py` 寫 `OpenAIWorthItSynthesizer` 紅測：注入假 poster 回反逢迎綜合 → 呼叫 chat、回綜合；poster 拋例外 → 拋 `OpenAIError`（教訓 3 邊界）。
- [X] T006 在 `src/knowfield/search/worthit.py` 加 `OpenAIWorthItSynthesizer`（`_post`、反逢迎 `_SYSTEM`：官方/獨立/用戶分開、明說炒作/缺點、只依 evidence＋附引用、某層查無說「沒搜到」、末給值不值得＋怎麼用、`poster` 可注入）；`backends/factory.py` 加 `make_worthit_synthesizer(config)`。跑 T005 轉綠。

**檢查點**：純函式產出獵心得 query、去重撒網、反逢迎綜合（grounded、有引用）；離線零外部呼叫。

---

## Phase 3：US1+US2+US3（P1）——web 路由、收內容口、subject 解析

- [X] T007 [P] 在 `tests/contract/test_worth_web.py` 寫路由紅測：注入假 `app.state.worth_factory` 回 `WorthItVerdict` → `POST /worth`（`subject` 名字）回 200＋`worth.html` 含綜合＋引用連結。
- [X] T008 [P] 寫**收內容口/subject 解析**紅測：①只給 `content`（內文）→ factory 收到由內文首行解出的 subject；②給抓不到的 `url`（假 fetch 拋例外）→ 不崩、退回用 url/名字續跑（factory 仍被呼叫）；③三者皆空 → 友善提示「請貼名字或內文」、不呼叫 factory。
- [X] T009 [US1] 在 `src/knowfield/web/app.py` 加 `app.state.worth_factory`（預設用 `make_web_search`＋`make_worthit_synthesizer` 建 `assess_worth`）＋ `GET /worth`（表單）＋ `POST /worth`（subject 解析序 name＞content 首行＞url 抓標題 best-effort＞url；呼叫 factory→render）。跑 T007/T008 轉綠。
- [X] T010 [US1] 建 `src/knowfield/web/templates/worth.html`（手機友善表單：textarea「貼名字或內文」＋選填 url；綜合呈現＋`sources` 引用清單；`no_material`→「太新/資料太少」）；`base.html` 導覽加「值不值得」入口。

**檢查點（US1/2/3 可獨立驗）**：/worth 丟名字/內文/抓不到的網址皆能回反逢迎綜合、有引用、手機友善。

---

## Phase 4：US4（P2）——失敗/空友善

- [X] T011 [P] [US4] 寫失敗友善紅測：`worth_factory` 拋 `SourceUnavailable` → `POST /worth` 回 200＋友善 `err`、不噴 Traceback。
- [X] T012 [P] [US4] 寫空結果紅測：`worth_factory` 回 `WorthItVerdict(no_material=True)` → 頁面顯示「太新/資料太少」。
- [X] T013 [US4] 在 `POST /worth` 加 `except (SourceUnavailable, OpenAIError)`→`_log.error`＋友善 `err`；`no_material` 友善訊息。跑 T011/T012 轉綠。

**檢查點**：搜尋/綜合失敗、空結果皆友善不崩。

---

## Phase 5：Polish & 回歸

- [X] T014 跑 `uv run pytest tests/unit/test_worthit.py tests/contract/test_worth_web.py -q` 全綠。
- [X] T015 跑 `uv run pytest -q` 全綠（現 307 + 本增量新測）；確認範圍守住（無場驅動關聯/收進 extension/moment B-C/K8s/CLI）。既有路由零回歸。
- [X] T016 真後端驗（若金鑰在）：重啟 server、`/worth` 丟「Claude Opus 5」→ 看反逢迎綜合真的分官方/獨立/用戶、明說炒作、有引用（呼應手動探針）。文件記 `cloudflared` tunnel 手機可達（ops、非功能）。

---

## 依賴與執行順序
- Foundational（T001–T006）阻塞路由。T004 阻塞 T009；T006（synthesizer）供真後端。
- US1/2/3（T007–T010）：路由＋模板，依 T004。
- US4（T011–T013）依路由就緒。
- Polish（T014–T016）最後。

## 平行機會
- T001‖T002‖T003‖T005（不同測案）；T007‖T008；T011‖T012。
- 實作 T004/T006（模組）、T009/T010（app＋模板）、T013（同路由）順序觸同批檔案，序執行。

## MVP
**T001–T010**＝丟名字/內文/網址 → 反逢迎綜合、收內容口、手機友善。US4 為友善邊界，薄。
