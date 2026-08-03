# 任務清單：問答併進聊天——聊天 ground 在核心理解＋收進的文章＋web

**規格**：[spec.md](./spec.md) ｜ **計畫**：[plan.md](./plan.md) ｜ **分支**：`029-chat-corpus-grounding`

TDD 強制：先紅後綠。**核心零新相依、無新表**（只讀既有語料/embeddings）。純函式 `retrieve_corpus`＋field-chat 注入塊為基石。最硬的一條＝**純度守門**（收進＝證言非地基）。優先序 US1（引用）＋US2（膜分層守純度）皆 P1、US3（問答退場）P2。

---

## Phase 1：Foundational（檢索純函式，阻塞 US1/US2）

- [X] T001 [P] `tests/unit/test_corpus_retrieve.py` 寫 `retrieve_corpus` 紅測：種數則收進條目＋注入 stub embedder（可控 cosine）→ 回相關命中（依 min_score 過濾、top_k 截斷、加權排序）；空語料→`[]`；全不相關→`[]`。
- [X] T002 `src/learnnews/rag/service.py`：抽出 `retrieve_corpus(repo, embedder, query, top_k, min_score)->list[CorpusEntry]`（list_corpus_entries→ensure_embeddings→embed→cosine→門檻→加權排序→top_k）；`RagService.answer` 改呼叫它（行為不變）。跑 T001＋既有 RAG 測轉綠。

**檢查點**：檢索純函式離線可測、RAG 既有行為不回歸。

---

## Phase 2：US1（P1）——聊天引用收進的文章

- [X] T003 [P] [US1] `tests/unit/test_chat_corpus_web.py` 寫紅測：注入 `corpus_search_for_test`（回幾則收進 hit）＋含 `[n]` 的 stub 回答 → `POST /chat`（非腦力激盪）→ 回應來源清單含**收進條目**（標 `kind=corpus`／「你收藏的」）、附 `[n]`；沒被引用的收進條目**不列**（cited-only）。
- [X] T004 [US1] `src/learnnews/chat/field_chat.py`：`_messages` 加 `corpus_contents` 參數→注入獨立 system 塊（「你收藏的資料（外部證言…別當地基）：[n] title — 摘錄」）；`reply`/`reply_stream` 透傳。`src/learnnews/web/app.py`：`_default_chat`＋`chat_stream` 非腦力激盪時 web 撒網後也 `retrieve_corpus`（best-effort、可注入 `corpus_search_for_test`），web＋收進**併成一個 sources 清單**（連號、帶 `kind`）＋組 `corpus_contents` 傳入；cited-only 濾。跑 T003 轉綠。
- [X] T005 [US1] `chat.html`：來源列依 `kind` 顯示（`corpus`→「📎 你收藏的」小標、`web`→原樣）；串流 `done` 與非串流渲染都吃到。

**檢查點**：聊天能引用收進條目、標「你收藏的」、cited-only。

---

## Phase 3：US2（P1）——膜分層＋純度守門（原則 6，最硬）

- [X] T006 [P] [US2] `test_chat_corpus_web.py` 寫**純度守衛**紅測：種一則含 `SECRET_外部觀點` 的收進條目 → 注入檢索回它 → `POST /chat` → 之後 `build_field_system_prompt(list_why_nodes("anointed"))` **不含** `SECRET_外部觀點`（收進不進地基）；且 `list_why_nodes` **不因引用而增**（不自動變核心理解）。
- [X] T007 [P] [US2] 寫膜分層紅測（單元）：`field_chat._messages(..., corpus_contents=[...含 SECRET])` → 組出的 system/messages 裡收進在「你收藏的」證言塊、而 `build_field_system_prompt(roots)` 段**不含** SECRET（地基只有核心理解）。
- [X] T008 [US2] `field_chat.py`：`_MEMBRANE` 加一句三層（核心理解＝地基／你收藏的＝證言（比核心理解軟）／web＝外部）；確認 `corpus_contents` **只**進注入塊、`build_field_system_prompt` 只吃 roots。跑 T006/T007 轉綠。

**檢查點**：收進以證言出現、絕不進地基、不自動變核心理解；膜提示分層。

---

## Phase 4：US3（P2）——問答併入、退場

- [X] T009 [P] [US3] 寫紅測：`GET /ask` → 302 導向 `/chat`；導覽（base.html 渲染）不含「問答」入口。
- [X] T010 [US3] `app.py`：`/ask` route 改 `RedirectResponse('/chat', 302)`（移除 RAG 頁邏輯，保留 RagService/retrieve_corpus）；`base.html` 導覽移除「問答」；刪 `ask.html` 與 /ask 的舊 web 測（檢索能力改由 chat 測涵蓋）。跑 T009 轉綠。

**檢查點**：問答入口退場、舊網址導向聊天、能力在聊天。

---

## Phase 5：Polish＋回歸

- [X] T011 [P] 寫 best-effort／fallback 紅測：`corpus_search_for_test` 拋例外 → 聊天照跑（只 核心理解＋web）、不 500；無收進語料 → 同樣照跑。腦力激盪模式 → 不檢索收進。
- [X] T012 全繁中檢查（注入塊/來源標記/膜提示）＋範圍守住（**無**檢索調參 UI、**無**跨文件多跳/全文搜尋、**無** PDF/影音進料、**無**收進自動變核心理解、**無** CLI）。
- [X] T013 跑 `uv run pytest tests/unit/test_corpus_retrieve.py tests/unit/test_chat_corpus_web.py -q` 全綠；再 `uv run pytest -q` 全綠（現 265 ＋ 本增量、扣掉退場的 /ask 測）；既有 spec 022/023/024/025/026/028 零回歸。

---

## 依賴與平行

- **檢索純函式（T001-T002）→ US1 引用（T003-T005）→ US2 膜分層/純度（T006-T008）→ US3 退場（T009-T010）→ Polish**。
- US1／US2 皆依檢索純函式；US2 的守衛是這功能的靈魂（收進≠地基）。
- **MVP＝US1＋US2**（引用得靠 US2 把關才安全，一體）。US3 退場為收斂。
- 紅測多可 `[P]`。
