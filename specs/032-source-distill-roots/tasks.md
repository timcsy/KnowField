# Tasks：spec 032 收進的活化——整理成核心理解

TDD 強制：每組先寫測試（紅）→ 實作（綠）。全離線（StubExtractor），零外呼。

## Phase 1：Setup
- [x] T001 確認 `make_root_cause_extractor`（`backends/factory.py`）與 `StubExtractor` 可用（既有，無需改）。

## Phase 2：Foundational（阻擋所有 US）
- [x] T002 [P] `app.state.extractor_factory = make_root_cause_extractor`（`web/app.py`，可注入）。

## Phase 3：US1 — 把一份收進整理成候選核心理解（P1）
- [x] T003 [US1] 測試 `tests/unit/test_source_distill.py`：`distill_source(repo, StubExtractor(), url)` → 存一條候選、`evidence_urls==[url]`、含 ladder/touchstones；`no_material`/空 claim → 回 None 不存；空來源 → None。
- [x] T004 [US1] 實作 `src/learnnews/ingest/activate.py::distill_source(repo, extractor, url)`（組材料→extract→存候選/回 None）。
- [x] T005 [US1] 測試 repo：`why_node_source_provenance()` — anointed root 的 evidence_url 命中現有來源→{wid:url}；未命中→不列。
- [x] T006 [US1] 實作 `repository.why_node_source_provenance()`。
- [x] T007 [US1] web 測 `tests/unit/test_source_distill_web.py`：`POST /source/distill?u=url`（注入 Stub）→ 候選出現在 `/roots`；冊封該候選後 `/roots` 顯示「由來（你收進的來源）」連 `/source?u=url`。
- [x] T008 [US1] route `POST /source/distill`（`web/app.py`）＋`source.html` 加「整理成核心理解」鈕＋`roots.html` 加來源由來連結。

## Phase 4：US2 — 純度守衛（P2）
- [x] T009 [US2] 守衛測（`test_source_distill.py` 或 web）：跑 `distill_source` 後 `list_why_nodes("anointed")` 不變；候選 status=='candidate'；`build_field_system_prompt(anointed)` 不含來源內容（收進不進地基）。

## Phase 5：US3 — 萃取失敗 best-effort（P3）
- [x] T010 [US3] web 測：注入會拋 `SourceUnavailable` 的 extractor → `POST /source/distill` → 導回 `/source` 顯示友善錯誤、原文仍在、非 500。
- [x] T011 [US3] route 攔 `SourceUnavailable`（`web/app.py`）→ `/source?u=url&err=…`；`source.html` 顯示 err。

## Phase 6：Polish
- [x] T012 全測綠、零回歸（336→新數）；繁中；真後端 smoke（可選，清測試資料）。
- [x] T013 knowie 固化：vision 階段 26 勾成、history 記完成、draft 反流退場。
