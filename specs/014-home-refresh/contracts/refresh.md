# Contract：首頁重新整理

## `app.state.digest_refresh_factory(config, repo) -> None`（`web/app.py`）
- 預設 `_default_digest_refresh`：啟用來源（空則種預設）→ `build_adapters` → `run_digest`
  （當前 UTC 日、`config.digest_limit`、`build_backend_builder(config)`）→ `repo.save_digest`。
- **可被測試覆寫**（注入 stub：存假 Digest 或拋錯）。

## `POST /digest/refresh`（新）
- **MUST** 呼叫 `app.state.digest_refresh_factory(config, repo)` → 成功後 `RedirectResponse("/", 303)`。
- **MUST** 攔 `SourceUnavailable`／`OpenAIError`／其他例外 → `RedirectResponse("/?msg=refresh_fail", 303)`
  （不 raise、非 500）；**舊匯整不受影響**（失敗未 save）。
- **MUST NOT** 新增/改資料表；**MUST NOT** 刪既有匯整（`save_digest` 是 append）。

## `GET /`（首頁擴充）
- **MUST** 讀 `msg` query；`msg=refresh_fail` → context 帶友善提示旗標。
- `digest.html`：頂端 `<form method=post action=/digest/refresh>`＋「🔄 重新整理」鈕＋**成本提示**
  （繁中：會抓最新並重新消化、需要一點時間）；`refresh_fail` → 顯示 alert。
- 面向使用者全繁中。

## 契約測試（離線、零外部呼叫）
1. 注入 stub factory（存一份新假 Digest）→ `POST /digest/refresh` → 303 導 `/` → `GET /` 顯示該最新匯整。
2. **不刪舊**：先有舊匯整 → 注入 stub 存新的 → 重整後 `list`/首頁最新是新的、舊的仍在 DB。
3. **失敗友善**：注入 factory 拋 `SourceUnavailable` → `POST /digest/refresh` 非 500、導 `/?msg=refresh_fail`；
   `GET /?msg=refresh_fail` 顯示友善提示、無 Traceback；舊匯整不受影響。
4. **鈕與成本提示**：`GET /` 頁面含 `action="/digest/refresh"` 表單＋成本提示字樣。
5. **不自動**：只 `GET /`（不 POST）→ 不觸發 refresh（factory 未被呼叫）。
