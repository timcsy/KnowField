# 實作計畫：反逢迎的「值不值得 follow」副手（時刻 A）

**分支**：`021-worth-it-verdict` ｜ **日期**：2026-07-28 ｜ **規格**：[spec.md](./spec.md)

## 摘要

丟一個新 AI 東西（名字／內文／網址）→ **多角度獵心得查詢**撒網 → 用搜尋結果的標題/摘要當心得證據
→ **反逢迎綜合**（官方/獨立/用戶分開、明說炒作、有引用、grounded）。核心價值在**兩段 prompt/邏輯**：
獵心得 query ＋ 反逢迎綜合；基礎設施（可插拔搜尋、LLM、RWD）全在。

**比 SmartSearch 更輕**（關鍵設計）：手動探針證明——心得證據來自**搜尋結果的標題/摘要本身**，
**不需**逐則抓內文、也不需嵌入排序。故新建一個精簡 `assess_worth`，不套 SmartSearch 全管線。

## Technical Context

**Language/Version**：Python 3.12+
**Primary Dependencies**：stdlib（urllib、`_post`）；web 層 FastAPI＋Jinja2（既有，不新增）
**Storage**：無（待判物/心得/綜合皆短暫、不落庫）
**Testing**：pytest（現 307 綠）
**Project Type**：web
**Constraints**：離線可注入替身零外部呼叫可測；grounded（有引用、沒料說沒料）；手機友善（RWD）

## Constitution Check

| 原則 | 判定 | 理由 |
|------|------|------|
| I. TDD | ✅ | 先寫紅測（獵心得 query 角度、綜合 grounded/反逢迎、收內容口三種輸入、失敗友善）再實作 |
| II. 全繁中 | ✅ | 頁面、綜合、錯誤全繁中 |
| III. 規格驅動 | ✅ | spec 021→plan→tasks→impl，可追溯 FR |
| IV. 簡潔／YAGNI | ✅ | **核心零新相依**；一精簡模組＋一路由＋一模板；串既有零件；不套 SmartSearch 全管線 |
| V. 可觀測／錯誤處理 | ✅ | 搜尋/抓取/綜合失敗 `_log.error`＋友善繁中（教訓 3） |
| VI. 使用者決策主權 | ✅ | 反逢迎＝不順著行銷（原則 6）；產物不落庫（原則 5） |

**無違反、無複雜度追蹤項。**

## 技術方案

### 新模組 `src/knowfield/search/worthit.py`
```
def worthit_queries(subject: str) -> list[str]      # 獵心得多角度（模板、確定性、可測）
    # 心得/評價、review reddit、vs 缺點 complaints、值得嗎 limitations、怎麼用 how to use

@dataclass WorthItVerdict:
    subject: str; verdict_md: str; sources: list[SearchResult]; no_material: bool

class WorthItSynthesizer(Protocol): def synthesize(subject, evidence: list[SearchResult]) -> str
class StubWorthItSynthesizer   # 離線確定性、零外部呼叫
class OpenAIWorthItSynthesizer # _post，反逢迎 _SYSTEM，poster 可注入

def assess_worth(web_search, synthesizer, subject: str, *, content: str|None=None,
                 result_cap: int = 12) -> WorthItVerdict
```
流程（精簡、不逐則抓內文）：
1. **獵心得 query**：`worthit_queries(subject)` 出多角度（模板確定性 → 離線可測；不查通用名）。
2. **撒網**：對每 query `web_search.search(q, news=False)`；蒐集結果、按 url 去重、cap。失敗→`SourceUnavailable`。
3. **無結果** → `no_material=True`（綜合誠實說「太新/資料太少」）。
4. **反逢迎綜合**：`synthesizer.synthesize(subject, evidence)`——system prompt 明令：**官方/獨立/用戶
   分開**、**明說炒作/缺點/難搞**、**只依證據＋附引用、沒料說沒料**（grounded，原則 3/教訓 7）。

### 主題識別（收內容口，FR-002/007）
- 路由收三種輸入：`name`（短文字）／`content`（客戶端內文，牆內）／`url`。
- **subject 解析序**：明給 name ＞ content 首非空行（截斷）＞ url 可抓到的標題 ＞ url 本身。
- **伺服器抓＝best-effort**：有 url 且無 name/content 時，`fetch_url`（既有）取標題**包 try/except**
  （403/牆內→退回用 url／名字，**不崩**）。**關鍵洞察落地**：只要有 subject 字串就能跑，抓不到不阻斷。

### Web 路由 `POST /worth` ＋ `GET /worth`
- `GET /worth`：手機友善表單（一個 textarea「貼名字或內文」＋選填 url）。
- `POST /worth`：解析 subject（上序）→ `app.state.worth_factory(subject, content)`（預設用
  `make_web_search`＋`make_worthit_synthesizer` 建 `assess_worth`；測試覆寫）→ render `worth.html`
  加 `verdict`。空/失敗→友善（`SourceUnavailable`/`OpenAIError`→`_log.error`＋友善）。
- `base.html` 導覽加「值不值得」入口。

### backends/factory.py
- `make_worthit_synthesizer(config)`：`openai`＋key → `OpenAIWorthItSynthesizer`；否則 `StubWorthItSynthesizer`。

### 反逢迎 _SYSTEM（核心價值）
明令：分**官方說法／獨立評測／真實用戶心得**三層；**標出炒作、缺點、難搞**、不粉飾；**只依提供的
搜尋證據、每點附引用 url、某層查無就說「沒搜到」**、不杜撰；末給「值不值得你＋怎麼用才發揮」。

**不動**：`websearch.py`、`answerer.py`、`smart.py`、`expand.py`、`seed/fetch.py`、schema。

## Project Structure

### 受影響檔案
```text
src/knowfield/search/worthit.py              # 新：queries + WorthItVerdict + Synthesizer + assess_worth
src/knowfield/backends/factory.py            # make_worthit_synthesizer
src/knowfield/web/app.py                      # GET/POST /worth + worth_factory
src/knowfield/web/templates/worth.html        # 新：手機友善表單 + 綜合呈現
src/knowfield/web/templates/base.html         # 導覽加「值不值得」入口
tests/unit/test_worthit.py                    # queries/synthesize/assess_worth/subject 解析
tests/contract/test_worth_web.py              # 路由：三種輸入/收內容口/失敗友善/抓不到不崩
```

## 複雜度追蹤
無。核心零新相依、零新表；串既有可插拔零件；不逐則抓內文（比 SmartSearch 更省）。

## 部署（非本 spec 功能，記一筆）
手機搆得到＝ops：`cloudflared tunnel --url http://localhost:8000` 指向本機。**out：K8s/Helm**
（`部署與介面路線` draft 已擱置）。本 spec 只確保頁面 RWD＋收內容口讓手機送得進來。
