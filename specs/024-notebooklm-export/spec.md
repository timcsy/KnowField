# Feature Specification: 匯出給 NotebookLM（複製 Markdown＋複製佐證網址）

**Feature Branch**: `024-notebooklm-export`

**Created**: 2026-07-29

**Status**: Draft

**Input**: User description: "匯出對話／根因給 NotebookLM——三個匯出點（/chat、/conversations/{id}、/roots）各加兩顆鈕：📋 複製 Markdown、🔗 複製佐證網址；純匯出唯讀、可測純 formatter、TDD、繁中"

## 由來與定位（為何做這個）

使用者用了 `/chat`（有根據聊＋反逢迎的膜）後回饋「會一直想用」，接著問：**這樣不會跟 NotebookLM 很重疊嗎？** 定調——**不是競爭是接力**：這工具做**膜／蒸餾**（護城河），NotebookLM 做**打磨過的輸出**（audio overview／study guide）；**不重蓋 audio**，而是把工具的產物**匯出**、讓 NotebookLM 接力。

要匯出**兩種料**，對應 NotebookLM 的兩種吃法：

1. **蒸餾內容**（對話／根因的文字＋階梯＋引用）→ 貼成 NotebookLM 的**文字來源**。這是**真價值**——NotebookLM 抓不到（它活在使用者本機的場裡），只能餵它。
2. **佐證網址清單**（被引用的來源 URL）→ 當 NotebookLM 的 **URL 來源**，它自己去抓。只是原始佐證、且抓網址會踩 paywall/403，當**附帶**。

使用者定案：「**複製 Markdown 和複製佐證網址都要，這樣才能都丟給 NotebookLM**」。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 把一段對話複製成 Markdown 丟進 NotebookLM（Priority: P1）

使用者在跟場聊完（`/chat`）或翻看一段存下的對話（`/conversations/{id}`）時，想把這段**蒸餾過的內容**帶去 NotebookLM 生 audio／study guide。他按一顆「📋 複製 Markdown」鈕，整段對話（含每則發言、行末 `[n]` 引用、底部來源清單）就以乾淨 Markdown 進了剪貼簿，直接貼進 NotebookLM 當文字來源即可閱讀。

**Why this priority**: 這是整個接力的**核心價值**——蒸餾內容是 NotebookLM 抓不到、只能由本工具提供的東西。少了它，匯出只剩書籤清單，工具的膜／蒸餾就白費。單獨實作這條即可交付：使用者能把場的產物帶進 NotebookLM。

**Independent Test**: 對一段已存在的對話（含含來源與不含來源的訊息）按「複製 Markdown」，驗證剪貼簿內容為一段結構正確、可讀的 Markdown（標題、發言者標示、行末引用、底部來源清單）；後端純 formatter 可離線單測。

**Acceptance Scenarios**:

1. **Given** 一段有多則 user/assistant 發言、其中 assistant 訊息帶來源的對話，**When** 使用者按「📋 複製 Markdown」，**Then** 剪貼簿得到一段 Markdown：含對話標題、每則發言依角色標示、帶來源的段落保留行末 `[n]`、結尾有「來源」清單（`[n] 標題 — URL`）。
2. **Given** 一段沒有任何來源的純聊對話，**When** 按「複製 Markdown」，**Then** 得到不含「來源」區塊、但其餘結構完整的 Markdown，不報錯。
3. **Given** 使用者在 `/chat` 頁聊到一半（對話在前端 history），**When** 按「複製 Markdown」，**Then** 當前整段對話被複製，內容與 `/conversations` 存檔後複製的結果一致。

---

### User Story 2 - 把佐證網址清單複製丟進 NotebookLM（Priority: P2）

使用者想讓 NotebookLM 自己去抓那些被引用的原始來源。他按「🔗 複製佐證網址」，該對話裡**被引用到的**來源 URL 就每行一個進了剪貼簿，貼進 NotebookLM 的「新增網址來源」即可。

**Why this priority**: 附帶價值——補上原始佐證，但 NotebookLM 抓網址會踩 paywall/403，且這些是它本來也找得到的東西。次於 US1，但使用者明確要求兩顆都要。

**Independent Test**: 對一段帶多個來源的對話按「複製佐證網址」，驗證剪貼簿為去重、每行一個 URL 的純文字清單；後端純 formatter 可離線單測（含無來源→空清單不報錯）。

**Acceptance Scenarios**:

1. **Given** 一段對話其 assistant 訊息共引用了數個來源（可能跨訊息重複），**When** 使用者按「🔗 複製佐證網址」，**Then** 剪貼簿得到**去重後、每行一個 URL** 的純文字。
2. **Given** 一段沒有任何來源的對話，**When** 按「複製佐證網址」，**Then** 得到空內容（或明確的「無佐證網址」提示），不報錯。

---

### User Story 3 - 從一條冊封根因匯出（Markdown＋網址）（Priority: P3）

使用者在 `/roots` 看自己冊封的根因時，想把某條根因（主張＋階梯＋佐證）帶進 NotebookLM。每條根因下也有「📋 複製 Markdown」與「🔗 複製佐證網址」兩顆鈕：Markdown＝主張＋分層階梯＋佐證清單；網址＝該根因的佐證 URL 每行一個。

**Why this priority**: 根因是場的地基、最精華的蒸餾物，值得能單獨帶走；但對話匯出（US1/2）是使用者當下最直接的需求，根因匯出次之。

**Independent Test**: 對一條含主張、階梯、佐證的根因按兩顆鈕，分別驗證 Markdown 結構與 URL 清單；純 formatter 離線可測。

**Acceptance Scenarios**:

1. **Given** 一條已冊封、含主張與分層階梯與佐證 URL 的根因，**When** 使用者按「📋 複製 Markdown」，**Then** 剪貼簿得到含主張、階梯、佐證清單的乾淨 Markdown。
2. **Given** 同一條根因，**When** 按「🔗 複製佐證網址」，**Then** 得到該根因佐證 URL 每行一個、去重的清單。

---

### Edge Cases

- **空對話／缺欄位**：對話沒有訊息、或某訊息缺 `sources`／`content` 欄位 → formatter 給合理輸出（略過缺項），不崩（教訓 3）。
- **來源缺標題或缺 URL**：Markdown 來源清單以現有欄位盡量呈現（缺標題用 URL 代）；佐證網址清單只收有 URL 的項。
- **重複來源**：同一 URL 在多則訊息被引用 → 網址清單去重；Markdown 的底部來源清單以該對話的來源編號為準呈現。
- **複製失敗**（瀏覽器不允許 clipboard）→ 前端給明確繁中提示，不靜默失敗。
- **純匯出、不改任何狀態**：按鈕只讀既有資料組字串，不寫庫、不改場、不觸發任何場脈絡注入。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系統 MUST 在 `/chat`（當前對話）、`/conversations/{id}`（存下的對話）、`/roots`（每條冊封根因）三處各提供「複製 Markdown」與「複製佐證網址」兩個動作。
- **FR-002**: 「複製 Markdown」MUST 把該對話組成一段乾淨 Markdown：含**標題**、每則發言**依角色標示**、帶來源的段落**保留行末 `[n]` 引用**、結尾附**來源清單**（`[n] 標題 — URL`）；根因版本 MUST 含**主張＋分層階梯＋佐證清單**。
- **FR-003**: 「複製佐證網址」MUST 把該對話／根因中**被引用到的來源 URL** 以**去重、每行一個**的純文字提供。
- **FR-004**: 兩個動作 MUST 把結果**複製到剪貼簿**，並給使用者**複製成功的可見提示**；複製失敗時給明確繁中提示、不靜默失敗。
- **FR-005**: 組裝 Markdown 與網址清單的邏輯 MUST 是**純函式**（給定對話／根因資料 → 字串／清單），**不需外部呼叫（LLM／網路）**、可離線單測。
- **FR-006**: 匯出 MUST 為**純唯讀**：不修改任何既有資料、不改場、**不把任何內容注入回未來對話的場脈絡**（不觸 principle 6 的污染面）。
- **FR-007**: formatter 對**空對話／無來源／缺欄位** MUST 給合理輸出、不拋例外（教訓 3）。
- **FR-008**: 所有新增介面文字與提示 MUST 為繁體中文（憲章 II）；核心組裝邏輯 MUST 零第三方相依（憲章 IV）。
- **FR-009**: 本功能 MUST NOT 新增資料表或改動既有 schema——只讀既有 `conversations`／`why_nodes`（教訓 8）。

### Key Entities *(include if feature involves data)*

- **對話（Conversation）**：既有實體（spec 023）。含標題、訊息序列（每則 role／content／可選 sources）。本功能**只讀**它。
- **根因（Why node）**：既有實體。含主張、分層階梯（derived/empirical/applied）、佐證。本功能**只讀**它。
- **佐證來源（Source）**：對話訊息／根因下的來源項（編號、標題、URL）。匯出的兩種產物都由它衍生。
- **匯出產物（Markdown 字串／網址清單）**：**衍生值、不落庫**——即時由上述實體組出、送進剪貼簿。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 使用者能在 `/chat`、`/conversations/{id}`、`/roots` 三處**各一鍵**複製出可貼進 NotebookLM 當**文字來源**的乾淨 Markdown（含引用與來源清單）。
- **SC-002**: 使用者能在同三處**各一鍵**複製出可貼進 NotebookLM 當 **URL 來源**的佐證網址清單（每行一個、去重）。
- **SC-003**: 對話→Markdown、對話→網址清單、根因→Markdown／網址的組裝皆為純函式，**離線可單測**，且對空／缺欄位輸入**不崩**。
- **SC-004**: 匯出全程**不改動任何既有資料、不改場、不注入回對話**（有守衛測證明匯出後場脈絡不變）。
- **SC-005**: 全繁中；核心零相依；**現有 368 測試不回歸**、且新增涵蓋上述純函式與唯讀性的測試。

## Assumptions

- 對話與根因資料沿用既有結構（spec 022/023 的 `conversations`、既有 `why_nodes`）；本功能不需新表。
- 「被引用的來源」以既有渲染慣例為準（assistant 訊息以 `[n]` 標記、對應該訊息／根因的 sources 項）。
- 剪貼簿複製沿用既有 `.mathcopy` 前端 clipboard 模式（同專案既有機制）。
- 使用者手動把複製內容貼進 NotebookLM；本功能不與 NotebookLM 直接串接。

## Out of Scope（明確排除，防蔓延）

- 下載 `.md` 檔（本版只複製到剪貼簿）。
- 用 LLM 把對話洗成更順的「蒸餾 brief」來源（fast-follow）。
- 直接推進 NotebookLM API／自動同步。
- 對話全文搜尋、跨對話關聯／多跳。
- CLI。
