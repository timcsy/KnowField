# Feature Specification: 收進來源的管理／原文檢視／清理／rich-paste 圖片（spec 031）

**Feature Branch**: `031-source-management`
**Created**: 2026-08-04
**Status**: Draft
**Input**: 真實使用照出 spec 030 進料的四個問題：①一篇被切 N 塊、知識庫每塊佔一行「很難管理」；②「看不到原文」；③貼上的網站雜訊（導覽/評論/UI 文字）要過濾；④原文圖片也想帶進來（走 rich-paste）。核心＝把「一次進料」當**一份來源**（同 `url` 的塊歸一體），管理/檢視用來源、檢索仍用塊。**零新表**（靠既有 `url` 分組）。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 知識庫按「來源」管理，不再一篇 N 行 (Priority: P1)
使用者收進一篇長文（被切成 N 塊）後，「知識庫」頁只顯示**一列**（如「深入解析 Flow Matching（28 塊）」），可整篇刪除、整篇標解說文。

**Why this priority**: 最痛——現在一篇 28 行完全沒法管理。
**Independent Test**: 貼一段長文收進 → 知識庫只多一列、顯示塊數；按刪除 → 該來源所有塊與 embedding 一起消失。
**Acceptance Scenarios**:
1. **Given** 收進一篇被切 N 塊的來源，**When** 開知識庫，**Then** 只見一列、標「N 塊」、非 N 列。
2. **Given** 該來源一列，**When** 按刪除，**Then** 其 N 塊全刪、`/chat` 不再引用它。
3. **Given** 該來源一列，**When** 標解說文，**Then** 整篇（所有塊）都標為解說文。

### User Story 2 - 點進去看原文 (Priority: P1)
使用者點知識庫的一列 → **來源詳情頁**顯示整篇內容（把塊拼回、render markdown），含標題與原始連結。

**Why this priority**: 「看不到原文」——收了卻讀不到，無法回顧。
**Independent Test**: 收一篇 → 點進去 → 看到整篇 render 後的內容（不是 N 個片段、無明顯重疊重複）。
**Acceptance Scenarios**:
1. **Given** 一個來源，**When** 點它，**Then** 詳情頁顯示拼回的整篇（去除塊間重疊）、render 成好讀格式。
2. **Given** 內容含 markdown 圖片語法，**When** 檢視，**Then** 圖片顯示出來。

### User Story 3 - rich-paste：帶結構與圖片、濾掉網站雜訊 (Priority: P1)
使用者在網頁全選複製、貼進 LearnNews，收進來的是**乾淨的正文＋圖片**——導覽/評論/UI 文字被剝掉、原文圖片以行內圖顯示。

**Why this priority**: 直接解決「雜訊」＋「圖片」；rich-paste 一石多鳥（擷取貼上的 HTML → 抽正文 markdown＋圖片）。
**Independent Test**: 用含 nav/script/footer/`<img>` 的 HTML 模擬貼上 → 收進的 markdown 不含 nav/footer、含 `![](圖片url)`；詳情頁圖片顯示。
**Acceptance Scenarios**:
1. **Given** 貼上一段網頁 HTML（含導覽、正文、圖片、頁尾），**When** 收進，**Then** 內容只含正文（標題/段落/清單/圖片）、不含導覽與頁尾。
2. **Given** 純文字貼上（沒有 HTML），**When** 收進，**Then** 照舊當純文字收（向後相容）。

### User Story 4 - LLM 深度清理（選用、謹慎不改寫） (Priority: P2)
結構抽取仍留殘渣時，使用者可按「清理」讓 LLM 把貼上內容整理成**乾淨文章 markdown**——嚴格「只剝 UI、逐字保留正文」，預設不自動跑（避免擅自改寫）。

**Why this priority**: 結構抽取擋不掉的雜訊（穿插的推薦、標籤）交給 LLM；但「捕捉」工具要防幻覺改寫，故選用。
**Independent Test**: 注入 stub backend，`clean_markdown` 把夾雜的雜訊行去掉、保留正文；backend 失敗→退回原文（best-effort）。
**Acceptance Scenarios**:
1. **Given** 一段夾雜 UI 字的內容，**When** 按「清理後收進」，**Then** 收進的是去雜訊的正文。
2. **Given** LLM 後端失敗，**When** 清理，**Then** 退回未清理原文、不擋收進。

### Edge Cases
- 去重疊拼回：塊間 40 字重疊，詳情頁需去重、不重複顯示。
- 舊單篇種子（arxiv /ingest，1 塊）：按 url 分組＝一列一塊，照樣管理/檢視。
- 圖片 URL 失效/403：詳情頁該圖顯示不出＝可接受（v1 走 hotlink，非下載存檔）。
- rich-paste 抓不到 HTML（只有純文字）：退回純文字路。

## Requirements *(mandatory)*
- **FR-001**: 知識庫 MUST 以「來源」（同 `url`）為單位列出，一來源一列、顯示塊數；不再一塊一列。
- **FR-002**: 刪除 MUST 以來源為單位——刪其所有塊與對應 embedding。標解說文 MUST 套用到該來源所有塊。
- **FR-003**: MUST 提供來源詳情頁：把該來源的塊依序拼回、**去除塊間重疊**、render markdown（含行內圖片）。
- **FR-004**: 貼上 MUST 支援擷取瀏覽器的 HTML（rich-paste）：抽出正文 markdown（標題/段落/清單/引言/圖片 `![](url)`）、剝除 nav/script/style/footer/aside 等 boilerplate；無 HTML 時退回純文字（向後相容）。
- **FR-005**: 正文抽取 MUST 把 `<img>` 轉成行內 markdown 圖片（保留來源圖片 URL）。
- **FR-006**: MUST 提供選用的 LLM 清理：嚴格「剝 UI、逐字保留正文、不改寫」；**預設不自動跑**；後端失敗→退回原文、不擋收進（教訓 3）。
- **NFR**: 憲章 IV 零相依（抽取/去重疊純 stdlib、LLM 走既有後端且可注入 stub）；**教訓 8 無新表**（靠既有 `url` 分組、圖片以行內 markdown URL 承載）；憲章 II 全繁中；憲章 I TDD 不回歸（現 311）。

## Key Entities
- **來源（Source，邏輯視圖，非新表）**：同一 `url` 的一組 `digest_entries` 塊＝一份來源。屬性：url、標題、塊數、source_class、拼回的內容。管理/檢視的單位；檢索仍以塊為單位。

## Success Criteria *(mandatory)*
- **SC-001**: 收進一篇被切 N 塊的來源後，知識庫只增一列（顯示塊數），非 N 列。
- **SC-002**: 點該列 → 看到拼回、render 的整篇，無明顯重疊重複。
- **SC-003**: 貼上含 nav/footer/`<img>` 的網頁 HTML → 收進不含 nav/footer、圖片以行內圖顯示。
- **SC-004**: 純文字貼上仍照舊可收（向後相容）。
- **SC-005**: 刪除一來源 → 其所有塊與 embedding 消失、`/chat` 不再引用。
- **SC-006**: LLM 清理為選用、失敗退回原文不擋；全流程零外呼可測；既有測試不回歸。

## Assumptions
- 零新表：來源＝同 `url` 塊的邏輯分組；圖片以行內 `![](url)` 承載於塊文（hotlink，非下載存檔）。
- rich-paste 由前端擷取 `clipboardData` 的 `text/html` 送後端；HTML→markdown＋圖片由既有 `extract_article_markdown`（擴充支援 `<img>`）於後端完成。
- 範圍外：圖片下載/本地存檔（v1 hotlink）、跨來源合併、來源重命名、瀏覽器擴充、YouTube。
