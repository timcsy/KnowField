# Quickstart：驗證 來源訂閱（階段 8）

前置：可 `uv run`；web 可起。

## 1. 加一個部落格
```bash
uv run uvicorn knowfield.web.app:app     # 開 http://127.0.0.1:8000/sources
```
在 /sources 貼一個部落格首頁或 RSS（如某研究者部落格）→ 系統探測 feed、實測有料→加入、啟用。

## 2. 自動帶入匯整
```bash
uv run knowfield digest        # 新加的來源會被一起抓取分診
```

## 3. 管理
在 /sources 停用一個來源（下次匯整不抓）、刪除一個、重新啟用。

## 4. 誠實邊界
貼一個沒有 RSS 的網址／壞網址 → 友善繁中提示、**來源清單未新增**。

## 5. 測試（TDD 驗收）
```bash
uv run pytest tests/unit/test_feed_discovery.py tests/contract/test_web_sources.py -q
uv run pytest -q      # 全套：新測綠燈 + 既有 177 不回歸
```

## 驗收對映
| 檢查 | 對映 |
|---|---|
| 貼 URL→探測+驗證有料才加 | FR-002/003、SC-001、US1 |
| 加的來源自動帶入匯整 | FR-005、SC-002、US1 |
| 停用/啟用/刪除 | FR-006、SC-003、US2 |
| 無 feed/無料→不加壞 | FR-004、SC-004、US3 |
| 同 feed 不重複 | FR-007、SC-005 |
| 離線可測、177 不回歸 | FR-010、SC-006 |
