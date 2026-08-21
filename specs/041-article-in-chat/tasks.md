# 任務：文章進 `/chat` 的視野（階段 37）

**測試為必要**（憲章 I）。基準：後端 484、前端 13。

## Phase 1：Foundational — 閘門先於功能

⚠️ FR-003／SC-003 是本規格存在的理由，先釘住。

- [X] T001 [P] 撰寫 `tests/contract/test_chat_article.py`：帶了文章的一輪之後，`distill` 的輸入 **MUST NOT** 含文章內容——**先確認失敗**
- [X] T002 [P] 撰寫 `tests/unit/test_field_chat_article.py`：未選文章時 `_messages()` 的輸出與現況**逐字相同**——**先確認失敗**

## Phase 2：US2／US3 — 分層與閘門（P1，先於 US1）

- [X] T003 [US2] 在 `field_chat.py::_messages` 加「文章層」：標明**AI 依你的核心理解生成的衍生物**、明說**不得蓋過核心理解**、與 roots／sources 分開陳述
- [X] T004 [P] [US2] 加測試：注入文字含分層標示；文章內容不出現在 roots／sources 區塊
- [X] T005 [US3] 確認注入**只在 `_messages`**、不寫回 `history`（結構保證），加測試釘住
- [X] T006 [P] [US2] bare 模式 MUST NOT 注入文章（它是知識庫衍生物）

## Phase 3：US1 — 帶著文章接著想（P1）

- [X] T007 [P] [US1] 契約測試：`/api/chat/stream` 接受 `article_id`，回答反映該文章內容——**先確認失敗**
- [X] T008 [US1] `web/app.py`：`/api/chat/stream` 與 `_stream_gen` 收 `article_id`、讀文章、傳進 `FieldChat`
- [X] T009 [US1] 注入長度上限（沿用 sources 的 cap 形狀）＋加測試
- [X] T010 [US1] 選到已刪除的文章 → 明確告知（憲章 V），加測試
- [X] T011 [US1] `ChatPage.tsx`＋`api.ts`：明確選文章帶入、顯示「已帶：<標題>」、可取消

## Phase 4：Polish

- [X] T012 `uv run pytest -q` 零回歸（> 484）＋ `cd frontend && npm run build`（**不是** tsc --noEmit）
- [ ] T013 用 `run-knowfield` 真跑：選一篇文章、講一個「讀完想到的」想法、看回答是否踩得到文章；並確認冊封候選出自你的話

## 相依

```
T001-T002（閘門測試）→ T003-T006（分層與結構保證）→ T007-T011（功能）→ T012-T013
```

## 實作策略

⚠️ **MVP 不是「只做 US1」**。US3（閘門）是本刀存在的理由——少了它，這個功能就是把 AI 的輸出
接回 AI 的輸入再沉澱成地基。US2（分層）擋的是 AI 拿自己的產物冒充使用者的想法。
三個 P1：US1 是價值、US3 是前提、US2 是約束。


---

## 執行結果（2026-08-21）

T001–T012 完成，T013（用 run-knowfield 開瀏覽器真看）待做。
後端 484 → **497**、前端 13 綠、`npm run build` 綠。

### 結構保證是免費的，但我第一版的測試沒有牙齒

FR-003 的保證來自一個既有事實：`distill()` 的輸入只由 `history` 串成，而文章注入在
`_messages()` 組裝的**臨時 system 訊息**裡 ⇒ 蒸餾那一步結構上看不到文章。**不用新機制。**

⚠️ 但第一版的閘門測試驗的是「呼叫端的 list 沒被改」——而 `_messages` 開頭就
`hist = list(history)` 複製了一份，**那是恆真命題**。拿「把文章 append 進 hist」的
錯誤實作去撞，**全綠通過**。

改寫成真正的不變式：**文章只能出現在 `system` 訊息，絕不在 user/assistant 回合**
（會被持久化、之後餵進 distill 的正是那些回合）。再撞一次 → 紅。

⚠️ 而且第一次「撞」本身也是無效的：append 的位置在 `messages += hist` **之後**，是 no-op。
⇒ **撞測試之前要先確認攻擊真的實作了那個 bug。**

### 一個靠測試抓到的真坑

`repository.get_article()` 回的是 **dict**，我卻寫了 `getattr(_a, "markdown", "")`
——**靜默取到空字串**：功能看起來在跑、標題變「（無標題）」、內文什麼都沒帶進去。
又是一次「不會變的訊號」。測試撞得到（已驗）。

### 誠實的保證邊界

本刀關**直接**路徑（文章 → 候選）。**間接**路徑仍開著：助理若在回覆裡引用文章，那段會進
`history`。要結構性擋住需要**段落級出處**（out of scope）。
ⓘ 同一條間接路徑對既有 `sources` 也成立且已被接受；差別是文章為 AI 產物，風險略高。
