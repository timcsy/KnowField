# 實作計畫：跟你的場聊天（moment B/C）

**分支**：`022-field-chat` ｜ **日期**：2026-07-29 ｜ **規格**：[spec.md](./spec.md)

## 摘要

多輪對話，AI 從使用者冊封的根因往下推、維持反逢迎的膜、報場-增量、提冊封候選（人按才寫回）、按需找
佐證。**核心價值＝一段「反逢迎的膜」system prompt**（讀場＋膜＋分層＋grounding＋提候選）——這是第一
風險（自動版能否複刻手動品質），故 spec 圍著它設計、且真後端質性驗收（SC-006）。

**幾乎全複用**：`_post`（chat，多輪＝messages list）、`list_why_nodes('anointed')`（讀場）、`make_web_search`
（佐證）、`add_why_node`+`anoint_why_node`（人閘門寫回）、Tailwind RWD。新程式＝一個 chat 抽象＋膜 prompt
組裝＋幾條薄路由＋一個對話頁。**核心零新相依、零新表**（對話短暫不落庫；只有人按冊封才寫既有 why_nodes）。

## Technical Context

**Language/Version**：Python 3.12+
**Primary Dependencies**：stdlib（urllib、`_post`）；web 層 FastAPI＋Jinja2（既有，不新增）
**Storage**：SQLite（沿用 `why_nodes`；對話短暫不落庫；人按冊封才 `add_why_node`+`anoint`）
**Testing**：pytest（現 322 綠）
**Project Type**：web（桌面深工優先；不牽手機/tunnel）
**Constraints**：離線可注入替身零外部呼叫可測；原則 5（人按才冊封、永不自動改 bedrock）；grounded

## Constitution Check

| 原則 | 判定 | 理由 |
|------|------|------|
| I. TDD | ✅ | 先寫紅測（膜 prompt 注入根因、chat 多輪、distill 候選、anoint 人閘門、cite 佐證、失敗友善）再實作 |
| II. 全繁中 | ✅ | 對話、膜指引、錯誤全繁中 |
| III. 規格驅動 | ✅ | spec 022→plan→tasks→impl，可追溯 FR |
| IV. 簡潔／YAGNI | ✅ | **核心零新相依/零新表**；串既有零件；對話短暫、歷史用 client 帶回（無 session 狀態機） |
| V. 可觀測／錯誤處理 | ✅ | 對話/搜尋/寫回失敗 `_log.error`＋友善繁中（教訓 3） |
| VI. 使用者決策主權 | ✅ | 原則 5：AI 提候選、**人按才冊封**、永不自動改 bedrock；佐證按需（不自動搜） |

**無違反、無複雜度追蹤項。**

## 技術方案

### 新模組 `src/learnnews/chat/field_chat.py`
```
class ChatBackend(Protocol): def reply(self, messages: list[dict]) -> str
class StubChatBackend      # 離線確定性、零外部呼叫（回可測的膜式回應）
# OpenAIChatBackend 放 openai_api.py（_post，poster 可注入）

def build_field_system_prompt(roots: list[WhyNode]) -> str
    # 膜指引 ＋ 場脈絡（roots 的 claim＋ladder 注入）

@dataclass CandidateDraft: claim: str; ladder: list[str]; evidence_urls: list[str]

class FieldChat:
    reply(history: list[dict], user_msg: str, roots) -> str          # 一輪對話
    distill(history: list[dict], roots) -> CandidateDraft            # 整理成冊封候選（結構化）
```

### 反逢迎的膜 system prompt（核心價值，第一風險）
`build_field_system_prompt` 明令（每條都是 FR-003/004 的落地）：
1. **從場往下推**：注入的根因（claim＋階梯）是你的 bedrock；回應要**援引某條根因往下推**，非通用先驗。
2. **標界線**：每個論點標 **grounded（從你的根因/證據推得）／猜／likely-wrong**。
3. **分三層且低層不借高層權威**：derived（可證）／empirical（觀察湧現）／applied（借結構的鷹架）——
   **不得**用「因為某某就這樣」讓 applied/empirical 冒充 derived 的必然。
4. **過度擬合檢查**：無實作 payoff 或預測/解釋力的抽象 → 標「過度抽象/留沙盒」，不冒充知識。
5. **攔外來逢迎**：夾帶的過度宣稱（如「唯一解/完全自洽」）→ 點出並反駁，不附和。
6. **建設性、可更新**：非一直敵對；使用者更好論證 → 認錯更新。
7. **每輪報場-增量**：接上哪條根因／可收斂／缺口／冊封候選。
8. **提冊封候選**：值得留的根因 → 用使用者語氣提候選（但**只提，冊封是人按**）。
`distill` 用結構化提示把對話蒸餾成 `CandidateDraft`（claim＋ladder＋可選 evidence_urls），供人審後冊封。

### Web 路由（薄，皆可注入 factory）
- `GET /chat`：對話頁（空對話＋場摘要：已冊封幾條根因）。
- `POST /chat`：`history`（hidden JSON）＋`message` → append user → `app.state.chat_factory(history, message)`
  （預設用 `make_chat_backend`＋`list_why_nodes('anointed')` 建 `FieldChat.reply`）→ append assistant →
  重繪對話＋更新 hidden history。**多輪狀態＝client 帶回 history**（無 server session，YAGNI）。
- `POST /chat/distill`：history → `FieldChat.distill` → 可編輯的冊封候選表單（claim/ladder/urls）。
- `POST /chat/anoint`：claim＋ladder＋urls → `repo.add_why_node(...)`+`anoint_why_node(id)` → 確認（可回 `/roots` 刪）。
- `POST /chat/cite`：`claim` → `make_web_search` 撒幾個佐證 query → 回附引用連結；查無誠實說沒搜到。
- `base.html` 導覽加「跟場聊」入口。

### backends/factory.py
- `make_chat_backend(config)`：`openai`＋key → `OpenAIChatBackend`；否則 `StubChatBackend`。

### 多輪狀態
- **client 帶回 history**（`chat.html` 用 hidden field 存 JSON、每 POST 帶回、server append 後重繪）——
  無 session 狀態機、stateless、無新表。過長時截斷保留近 N 輪（不崩）。

**不動**：`answerer.py`（一次性 RAG，不改）、`websearch.py`、`repository` 既有讀場/寫回、schema。

## Project Structure

### 受影響檔案
```text
src/learnnews/chat/field_chat.py             # 新：ChatBackend/Stub + build_field_system_prompt + FieldChat + CandidateDraft
src/learnnews/backends/openai_api.py         # + OpenAIChatBackend（_post 多輪、poster 可注入）
src/learnnews/backends/factory.py            # + make_chat_backend
src/learnnews/web/app.py                      # GET/POST /chat + /chat/distill + /chat/anoint + /chat/cite + factories
src/learnnews/web/templates/chat.html         # 新：桌面對話頁（history hidden field、場-增量、候選/佐證動作）
src/learnnews/web/templates/base.html         # 導覽加「跟場聊」入口
tests/unit/test_field_chat.py                 # 膜 prompt 注入根因/分層、reply、distill、cite
tests/contract/test_chat_web.py               # 路由：多輪、anoint 人閘門、cite、失敗/場空友善
```

## 複雜度追蹤
無。核心零新相依、零新表；串既有 chat/讀場/搜尋/寫回；對話短暫、歷史 client 帶回。

## 風險與驗收
- **第一風險（明列）**：自動版能否複刻手動品質——**價值全在膜 system prompt**。緩解：prompt 逐條對齊
  行為規格；**SC-006 真後端質性驗收**（對使用者真實的場對話，確認從根因推、標界線、分層、提可用候選）。
- 桌面優先 → 不牽手機/tunnel（降部署前置）。真驗收「複刻到讓使用者想餵場」超越測試綠。
