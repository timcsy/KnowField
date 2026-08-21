# 任務：來源英→繁一鍵全文翻譯（階段 34 第二刀）

**輸入**：[spec.md](./spec.md)、[plan.md](./plan.md)、[research.md](./research.md)、[data-model.md](./data-model.md)、[contracts/api-translate.md](./contracts/api-translate.md)

**測試為必要**（憲章 I，TDD 不可妥協）。**基準**：431 個 test 函式，完工零回歸。

---

## Phase 1：Setup

- [X] T001 建立 `src/knowfield/text/lang.py` 與 `src/knowfield/text/translate.py` 骨架（空模組）

## Phase 2：Foundational

- [X] T002 [P] 撰寫 `tests/unit/test_text_lang.py`：英文/中文/混排/空字串的 CJK 佔比判定（閾值 3%）——**先確認失敗**
- [X] T003 實作 `text/lang.py` 的 `is_english(text) -> bool`（純函式、零相依）

---

## Phase 3：User Story 4 — 承重內容不被翻譯破壞（P1）

⚠️ **先於 US1**：翻譯是生成式的，沒有這層保護，US1 會靜默吐出缺公式的譯文——比不翻更糟。

- [X] T004 [P] [US4] 撰寫 `tests/unit/test_text_translate.py`：backend 弄丟佔位符時該塊 MUST 逐字退回原文（不修補）——**先確認失敗**
- [X] T005 [US4] 在 `text/translate.py` 實作單塊流程：`protect.mask` → backend → **完整性檢查** → `protect.restore`；不完整回 `(原文, ok=False)`
- [X] T006 [P] [US4] 加測試：backend 拋例外時同樣降級為原文、不向外拋

## Phase 4：User Story 2 — 等待可接受且看得到進度（P1）

- [X] T007 [P] [US2] 撰寫並行測試於 `tests/unit/test_text_translate.py`：`translate_chunks` 回傳**塊數相同、順序一致**；單塊失敗不影響其他塊——**先確認失敗**
- [X] T008 [US2] 實作 `translate_chunks(chunks, backend, max_workers=8)`，形狀沿用 `summarize/article.py:18-32`（`ex.map`、單元素不開池、`min(max_workers, len)`）
- [X] T009 [US2] 加進度回呼參數（每完成一塊觸發），供 SSE 回報 `{done,total,failed}`

## Phase 5：User Story 1 — 一鍵看成中文（P1）

- [X] T010 [P] [US1] 撰寫 `tests/contract/test_web_translate.py`：SSE 事件序列 `stage*` → `done`，`done` 的塊數等於原文塊數（C-001）——**先確認失敗**
- [X] T011 [US1] 在 `web/app.py` 加 `GET /api/source/translate`（SSE），沿用 `_stream_gen` 的事件命名
- [X] T012 [US1] 在 `GET /api/source` 回應加 `is_english`（契約增補），既有欄位不動
- [X] T013 [P] [US1] 加契約測試 C-003：翻譯前後 `get_source_chunks(u)` 逐字相同（不寫回）
- [X] T014 [US1] 在 `SourcePage.tsx` 加「翻成繁中」動作，僅在 `is_english` 為真時顯示；接 SSE 顯示進度

## Phase 6：User Story 3 — 譯文不冒充原文（P1，憲章 VI）

- [X] T015 [US3] 在 `SourcePage.tsx` 顯示譯文時標明「**AI 翻譯**」，並提供切回英文原文
- [X] T016 [P] [US3] 加契約測試 C-005：非英文來源呼叫端點回 `error`（FR-009）

## Phase 7：Polish

- [X] T017 執行 `uv run pytest -q`，零回歸且總數 > 431（SC-006）
- [ ] T018 依 [quickstart.md](./quickstart.md) 用 `run-knowfield` 跑起來看：進度真的在動、公式正常渲染、AI 翻譯標示與原文出口都在、逐詞讀一段譯文
- [ ] T019 對 Lil'Log 那篇實測完成時間，確認 ≤ 2 分鐘（SC-002）

---

## 相依關係

```
T001 → T002-T003（語言）
     → T004-T006（保護，阻塞一切翻譯）
          → T007-T009（並行）
               → T010-T014（端點與前端）
                    → T015-T016（憲章 VI）
                         → T017-T019（驗證）
```

## 實作策略

⚠️ **MVP 不是「只做 US1」**。US4（保護）是 US1 的前提——沒有它，US1 會靜默丟失公式；
US3（標示與原文出口）是憲章 VI 的要求，缺了不能出貨。四個 P1 並列不是排序失誤：
US1 是價值、US4 是前提、US2 是可用性門檻（11 分鐘 = 等於沒有）、US3 是約束。

---

## 執行結果（2026-08-18）

T001–T017 完成，T018–T019 為真跑驗證（見下）。**462 測試全綠**（431 → +31）。

### ⚠️ 三次才寫出一條有牙齒的測試

FR-003（即時進度）的測試我寫了三版，前兩版都**撞不倒錯誤實作**：

| 版本 | 驗什麼 | 為什麼沒用 |
|---|---|---|
| 1：契約層，檢查「有沒有 stage 事件」 | 存在性 | 累積式實作也會吐 stage，只是全部翻完才吐 |
| 2：契約層，檢查「第一個事件是不是 stage」 | 順序 | 順序對、時機錯——累積式照樣第一個吐 stage |
| 3：單元層，**直接測產生器 + 時間上界** | **時機** | ✅ 拿累積式實作去撞會紅（2.12s 失敗） |

每一版我都拿一個**故意做成累積式**的實作去撞，前兩次都綠——那才發現測試沒有牙齒。
⇒ 判準：**一條沒有被錯誤實作撞過的測試，不知道自己在測什麼**。

同時也發現：時機這種東西**隔著 `TestClient` 驗不了**（它會緩衝）。所以把串流邏輯從路由抽到
`text/translate.py::translate_stream`——不是為了分層好看，是為了**讓時機測得到**。
路由只負責包 SSE。

### 真跑（T018–T019）

- 進度**確實即時串流**：SSE 逐筆吐出 `done` 從 1 數到 125，不是最後一次倒出。
- **SC-002 達標**：125 塊 **93 秒**（門檻 120s；序列基準 11.1 分 ⇒ **7.2 倍**加速）。
- **125 塊中 3 塊降級為原文**（2.4%）——保護片段完整性檢查如設計般生效，
  那 3 塊寧可不翻也沒有吐出缺公式的譯文。
- 譯文 23,710 字元。

⚠️ **我一度把這條寫成「未達標」，那是錯的**。第一次量測被 Bash 的 2 分鐘逾時砍斷在第 113 塊，
我把「命令逾時」讀成「功能超時」就寫進了這份文件。**工具的逾時不是被測系統的耗時**——
量測被中斷時唯一能下的結論是「沒量到」，不是「超過」。重測得 93 秒。
