# 技術方案：收進的活化——整理成核心理解（spec 032）

**分支/目錄**：`032-source-distill-roots` · **狀態**：Plan · **前置規格**：`spec.md`

## Technical Context

- 語言/框架：Python 3.12（uv）、FastAPI＋Jinja2、SQLite、stdlib 為主（承既有）。
- 接點：既有 `/source` 詳情頁、`/roots` 候選→冊封流、`rootcause` 萃取、`why_nodes` 表、由來機制。
- 憲章：II 全繁中；IV 核心零相依（萃取藏 `RootCauseExtractor` 介面後、離線 stub）。

## Constitution Check

- **IV 核心零相依**：萃取走既有 `make_root_cause_extractor`（真＝OpenAIExtractor urllib、測＝StubExtractor 離線確定性）。✅
- **II 全繁中**：UI 與訊息全繁中。✅
- **原則 5/6 + 階段 24 守衛**：只產候選、人閘門冊封、收進不進地基（守衛測）。✅
- **教訓 1/3/8**：萃取後端可注入離線 stub；失敗 best-effort 攔在 route；**零新表/零 schema 改動**（見下）。✅

## Phase 0：Research（關鍵決策）

見 `research.md`。三個定案：

1. **用哪套萃取？→ `rootcause.extract(title, body)`，非 `field_chat.distill`。**
   規格輸入原寫「復用 field_chat.distill 改吃來源塊」，但實地讀 code：`rootcause/extract.py` 的 `RootCauseExtractor.extract(title, body) -> Candidate`（含 7 條試金石自我反駁＋ladder＋fog_flag＋no_material）**本來就是為「從一則材料抽候選根因」設計**，正中 FR-002/FR-003；`field_chat.distill` 吃對話 history、產較輕的 CandidateDraft（無試金石）。**改用 rootcause.extract**——且它正是 `/roots` 候選背後的機制，與「沿用既有候選→冊封流」完全一致。`make_root_cause_extractor(config)`（`backends/factory.py`）已備雙後端、休眠待接。

2. **源→根因由來連結？→ 復用 `evidence_urls`，零 schema 改動（教訓 8）。**
   `add_why_node(claim, evidence_urls, …)` 已存 evidence_urls；整理來源時把**該來源 url 放進 evidence_urls**，這條 url 就是「由來（收進的來源）」。`/roots` 已渲染 `evidence_urls`。再加一個讀端衍生 `why_node_source_provenance()`：把「evidence_url 命中現有來源」映成 `{wid: url}`，`/roots` 顯示「← 由來（你收進的來源）」連到 `/source?u=url`。**不加欄、不改既有表語義**（優於規格假設的「加 nullable 欄」——連加欄都不用）。來源刪除後連結自然消失＝優雅（FR-010）。

3. **候選落點？→ 存進 `why_nodes`（status='candidate'），走既有 `/roots` 審閱。**
   `distill 來源` → `add_why_node(...)` 存候選 → 導 `/roots`。冊封走既有 `whynode_anoint`（不動）。純度守衛天然成立：`build_field_system_prompt` 只吃 `list_why_nodes("anointed")`，候選進不了地基。

## Phase 1：Design

### 資料模型（data-model.md）
**零改動。** 復用 `why_nodes`（candidate/anointed、evidence_urls、ladder、touchstones、fog_flag）。無新表、無新欄。

### 介面/元件
- **新** `src/knowfield/ingest/activate.py`：`distill_source(repo, extractor, url) -> Candidate | None`——取 `get_source_chunks(url)`＋`source_title(url)` 組材料 → `extractor.extract(title, body)` → 若 `no_material` 或空 claim 回 None（不硬編）；否則 `add_why_node(claim, evidence_urls=[url], touchstones, fog_flag, 0, now, ladder)` 存候選、回 Candidate。純函式風格、extractor 注入、離線可測。萃取失敗 → 讓 `SourceUnavailable` 冒出（route 攔）。
- **新** `repo.why_node_source_provenance() -> {wid: url}`：anointed roots 中 evidence_urls 命中現有 `list_source_groups()` url 者。
- **新 route** `POST /source/distill`（`u=url`）：呼叫 service → 成功導 `/roots?msg=…`（「整理出 N 條候選核心理解，請檢視」）；`SourceUnavailable`/無料 → 導回 `/source?u=url&err=…`（教訓 3，不 500）。
- **`app.state.extractor_factory`** = `make_root_cause_extractor`（預設），測試注入 Stub。
- **source.html**：加「整理成核心理解」按鈕（POST /source/distill）＋err 顯示。
- **roots.html**：anointed 段落，若 `source_provenance[w.id]` 有值 → 顯示「← 由來（你收進的來源）」連 `/source?u=url`（與既有對話由來並存）。

### 對外用語（FR-008）
按鈕/訊息只「整理成核心理解／候選／由來」，不露 distill/anoint/why-node。

## 測試策略（TDD）
- 單元：`distill_source` 給 stub extractor → 存候選、evidence=[url]、no_material→None（`test_source_distill.py`）。
- 守衛：整理只產候選、不動 anointed、收進不進地基（延續 `TestPurityGuard` 樣式）。
- repo：`why_node_source_provenance` 命中/未命中。
- web：`POST /source/distill` → 候選出現在 /roots；冊封後 /roots 顯示來源由來連結；萃取失敗→/source 不 500。
- 全部離線（StubExtractor），零外呼（教訓 1）。
