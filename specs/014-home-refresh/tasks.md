# Tasks：首頁重新整理（從 web 重跑分診）

**功能目錄**：`specs/014-home-refresh/`　｜　**TDD 強制**　｜　基準測試：243（不回歸）

依 spec 的 US 分期。`[P]`＝可並行（不同檔、無未完成相依）。

## Phase 1：Setup

- [x] T001 唯讀盤點復用點：`cli/digest_cmd.py` `run_digest`／`build_backend_builder`、
  `cli/fetchers.py` `build_adapters`／`DEFAULT_SOURCES`、`repo.save_digest`／`list_sources`、
  `web/app.py:139` `home`＋`:131` 全域 `OpenAIError` 攔截器、`templates/digest.html`。

## Phase 2：US1 一鍵重整＋US3 失敗友善（P1/P2，核心閉環）

> 獨立測試：POST /digest/refresh（注入 stub factory）→ 存新匯整→首頁顯最新；factory 拋 → 友善非 500、舊匯整不動。

### 測試先行（TDD）
- [x] T002 [P] [US1] `tests/contract/test_refresh.py`：注入 `app.state.digest_refresh_factory`
  （存一份新假 `Digest`）→ `POST /digest/refresh` 回 303 導 `/` → `GET /` 顯示該最新匯整。
- [x] T003 [P] [US1] `tests/contract/test_refresh.py` 續：**不刪舊**——先有舊匯整、注入 stub 存新的 →
  重整後首頁顯新、舊的仍在 DB。
- [x] T004 [P] [US3] `tests/contract/test_refresh.py` 續：注入 factory 拋 `SourceUnavailable` →
  `POST /digest/refresh` **非 500**、導 `/?msg=refresh_fail`；`GET /?msg=refresh_fail` 顯示友善提示、
  無 `Traceback`；舊匯整不受影響。
- [x] T005 [P] [US2] `tests/contract/test_refresh.py` 續：`GET /` 含 `action="/digest/refresh"` 表單
  ＋成本提示字樣；只 `GET /`（不 POST）→ factory 未被呼叫（不自動）。

### 實作
- [x] T006 [US1] `web/app.py`：`_default_digest_refresh(config, repo)`（啟用來源→空則種 `DEFAULT_SOURCES`
  →`build_adapters`→`run_digest`（當前 UTC 日、`config.digest_limit`、`build_backend_builder`）→
  `save_digest`）；`app.state.digest_refresh_factory = _default_digest_refresh`。
- [x] T007 [US1] `web/app.py`：`POST /digest/refresh`——try 呼叫 factory → 成功 303 導 `/`；
  攔 `SourceUnavailable`／`OpenAIError`／其他 → 303 導 `/?msg=refresh_fail`（教訓 3）。
- [x] T008 [US2/US3] `web/app.py`：`home` route 收 `msg: str=""`→ context 帶 `refresh_fail` 旗標。
- [x] T009 [US1/US2] `templates/digest.html`：頂端加「🔄 重新整理」表單（POST `/digest/refresh`）
  ＋繁中成本提示；`refresh_fail` → 顯示友善 alert。

## Phase 3：Polish

- [x] T010 [P] 更新 `docs/usage.md`：首頁「重新整理」（一鍵重跑分診、免 CLI、成本提示、不自動）。
- [x] T011 全套 `uv run pytest` 綠、不回歸（≥243＋新測）；快速手測首頁重整（離線 stub）。
- [ ] T012 真跑抽查（可選，留使用者）：設金鑰 → 首頁按重新整理，看真抓＋消化出新匯整。

## 相依與 MVP

- **相依**：T006 → T007 → T008 → T009；測試（T002-T005）先於實作。
- **MVP**：T006/T007（重整→存→導頁）＋T009（鈕）＝可交付；T008 失敗提示緊接。
- **並行**：contract T002-T005 同檔 `[P]`（順序寫）。
- **範圍守恆**：**無串流進度、無自動/定時、無 UI 選日期/主題、無同日去重、無 CLI**；不新增/不改表。
