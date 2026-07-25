# Research：首頁重新整理（階段 12）

## R1：無新資料模型
- **決策**：不新增型別／表。重整＝呼叫既有 `run_digest` → `save_digest`（append 一份 `Digest`）。
- **理由**：復用整條 digest 管線與匯整保存（教訓 8）；`get_last_digest` 取最新 → 重整後首頁自然顯新。

## R2：同步 vs 串流
- **決策**：**同步**——POST `/digest/refresh` 內跑完整 `run_digest`（抓＋消化）再導回 `/`。
- **理由**：`DigestBuilder.build` 是一次回傳完整 `Digest`、**非 generator**；改串流要重構管線（大工），
  YAGNI。同步阻塞對「按一下等一下」可接受；串流即時進度列**後續**（需把 build 改可逐步回報）。
- **成本可見**：鈕旁明確提示「會抓最新並重新消化、需要一點時間」（FR-003）；明確 POST 動作、
  不自動定時（FR-002、原則 5）。

## R3：可注入（離線可測）
- **決策**：`app.state.digest_refresh_factory(config, repo)`——執行「建 adapters→run_digest→save_digest」。
  預設實作用真實後端；契約測試注入 stub（直接 `repo.save_digest(假 Digest)`、或拋錯測失敗）。
- **理由**：教訓 1——把「跑分診」藏在可覆寫點後，契約測試零外部呼叫綠燈。

## R4：預設實作細節
- **決策**：`_default_digest_refresh(config, repo)`：
  1. `sources = repo.list_sources(enabled_only=True)`；若空 → 種入 `DEFAULT_SOURCES` 再取。
  2. `adapters = build_adapters(sources)`。
  3. `date = 當前 UTC 日`（`datetime.now(timezone.utc)`，web app 可用；核心不改）。
  4. `run_digest(repo, adapters, date, limit=config.digest_limit,
     builder=build_backend_builder(config))` → 得 `Digest`。
  5. `repo.save_digest(digest)`。
- **理由**：完全比照 CLI `handle` 的組裝（`cli/digest_cmd.py`），只是不印終端、改存後導頁。

## R5：失敗攔截（教訓 3）
- **決策**：route 用 try 包 factory；`SourceUnavailable`／`OpenAIError`／其他例外 → 導 `/?msg=refresh_fail`
  （不 raise、非 500）。`home` 讀 `msg` → 顯示友善繁中提示。（`OpenAIError` 亦有全域友善頁攔截作後盾。）
  舊匯整不受影響（失敗時沒 `save_digest`）。
- **理由**：重整是加值動作，掛了不該讓首頁崩或吐堆疊；舊匯整仍在。

## R6：缺漏來源（憲章 V）
- **決策**：`run_digest`／`DigestBuilder.build` 已產出 `missing_sources`，`save_digest` 已存、
  `home`／`digest.html` 已顯示——**零額外工**，自然沿用。
- **理由**：可觀測性既有，重整只是再跑一次同管線。

## R7：UI
- **決策**：`digest.html` 頂端（熱詞區塊附近）一個 `<form method="post" action="/digest/refresh">`
  ＋鈕「🔄 重新整理」＋小字成本提示。`msg=refresh_fail` 時顯示 alert。
- **理由**：最小 UI；POST 表單＝明確動作。

## R8：範圍守恆
- 不做：串流進度、自動/定時刷新、UI 選日期/主題/limit、同日去重、CLI（已有）。
