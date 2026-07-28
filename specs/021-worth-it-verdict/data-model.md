# Data Model：反逢迎的「值不值得」副手

**不改 schema、不新增資料表。** 全部短暫記憶體物件、不落庫（原則 5）。

## 新實體

### `WorthItVerdict`（`search/worthit.py`，記憶體）
| 欄位 | 型別 | 說明 |
|------|------|------|
| `subject` | `str` | 認出的待判物（名字） |
| `verdict_md` | `str` | 反逢迎綜合（官方/獨立/用戶分開、明說炒作、值不值得＋怎麼用；markdown 文字） |
| `sources` | `list[SearchResult]` | 撒網取得的心得證據（標題/連結/摘要），供引用回核 |
| `no_material` | `bool` | 撒網幾乎無結果＝True（綜合誠實說「太新/資料太少」） |

## 沿用（不變）
- `SearchResult`（title/url/snippet，spec 009）——證據載體。
- 可插拔 `WebSearch`、LLM `_post`、`fetch_url`（best-effort 抓標題）——全既有，不動。

## 契約摘要
- `worthit_queries(subject) -> list[str]`：確定性多角度獵心得查詢。
- `assess_worth(web_search, synthesizer, subject, *, content=None, result_cap=12) -> WorthItVerdict`。
- `WorthItSynthesizer.synthesize(subject, evidence: list[SearchResult]) -> str`（Stub＋OpenAI）。
