# 任務清單：跟你的場聊天（moment B/C）

**規格**：[spec.md](./spec.md) ｜ **計畫**：[plan.md](./plan.md) ｜ **分支**：`022-field-chat`

TDD 強制：先寫紅測（Red）→ 實作轉綠（Green）。核心零新相依、零新表；串既有 chat/讀場/搜尋/寫回。

---

## Phase 1：Setup
（無——沿用既有 web/LLM/搜尋/讀場/寫回基礎設施；不新增相依。）

## Phase 2：Foundational（chat 抽象＋膜 prompt，阻塞路由）

- [X] T001 [P] 在 `tests/unit/test_field_chat.py` 寫 `build_field_system_prompt` 紅測：給 anointed roots（含 claim＋ladder）→ system prompt **含各根因的 claim/ladder**（場脈絡注入）＋膜指令關鍵詞（grounded/猜、derived/empirical/applied、過度抽象、場-增量、冊封候選、人按）；roots 空 → 註明「場還空/未接場」。
- [X] T002 [P] 在 `tests/unit/test_field_chat.py` 寫 `StubChatBackend` 紅測：給 messages → 回確定性繁中膜式回應、零外部呼叫。
- [X] T003 [P] 在 `tests/unit/test_field_chat.py` 寫 `FieldChat.reply` 紅測：注入假 ChatBackend（回傳收到的 messages 摘要）→ 確認組出的 messages＝`[system(場脈絡)] + history + [user]`（多輪脈絡）。
- [X] T004 建 `src/knowfield/chat/field_chat.py`：`ChatBackend` Protocol＋`StubChatBackend`＋`build_field_system_prompt(roots)`（8 條膜指令＋場脈絡注入）＋`@dataclass CandidateDraft`＋`FieldChat.reply(history, user_msg, roots)`。跑 T001/T002/T003 轉綠。
- [X] T005 [P] 在 `tests/unit/test_field_chat.py` 寫 `FieldChat.distill` 紅測：注入假 ChatBackend 回結構化候選 → 得 `CandidateDraft(claim, ladder, evidence_urls)`。
- [X] T006 [P] 在 `tests/unit/test_field_chat.py` 寫 `OpenAIChatBackend` 紅測：注入假 poster 回覆 → 呼叫 chat、回文；poster 拋例外 → 拋 `OpenAIError`（教訓 3）。
- [X] T007 在 `src/knowfield/chat/field_chat.py` 加 `FieldChat.distill`（結構化蒸餾提示）；`src/knowfield/backends/openai_api.py` 加 `OpenAIChatBackend`（`_post` 多輪、poster 可注入）；`backends/factory.py` 加 `make_chat_backend(config)`。跑 T005/T006 轉綠。

**檢查點**：膜 prompt 注入根因、多輪 reply、distill 出候選；離線零外部呼叫。

---

## Phase 3：US1+US2+US3（P1）——對話頁、從場推、人閘門冊封

- [X] T008 [P] 在 `tests/contract/test_chat_web.py` 寫多輪對話紅測：注入假 `app.state.chat_factory` → `POST /chat`（history＋message）回 200＋`chat.html` 含使用者訊息與回應＋更新後 hidden history；factory 收到 (history, message)。
- [X] T009 [P] 寫**場脈絡**紅測：預設 chat_factory 走真 `FieldChat`＋stub chat backend，DB 有冊封根因 → 送出後回應/prompt 反映有注入根因（用 spy backend 確認 system 含根因 claim）。
- [X] T010 [P] 寫**冊封人閘門**紅測：①`POST /chat/distill` 回可編輯候選；②`POST /chat/anoint`（claim/ladder/urls）→ `list_why_nodes('anointed')` 多一條、可回；③`POST /chat` 與 `/chat/distill` **不寫** why_nodes（送出對話後冊封數不變，證不自動 capture）。
- [X] T011 [US1] 在 `src/knowfield/web/app.py` 加 `app.state.chat_factory`（預設 `FieldChat.reply` with `make_chat_backend`＋`list_why_nodes('anointed')`）＋`distill_factory`＋`GET /chat`（頁）＋`POST /chat`（append→factory→重繪＋更新 hidden history）。跑 T008/T009 轉綠。
- [X] T012 [US3] 加 `POST /chat/distill`（→候選表單）＋`POST /chat/anoint`（`add_why_node`+`anoint`，人閘門；`_now_iso` 日期）。跑 T010 轉綠。
- [X] T013 [US1] 建 `src/knowfield/web/templates/chat.html`（桌面對話串：user/assistant 泡泡、hidden history JSON、輸入框；對話下「整理成冊封候選」→候選表單含「冊封」；每則 assistant 下「找佐證」鈕佔位）；`base.html` 導覽加「跟場聊」。

**檢查點（US1/2/3 可獨立驗）**：/chat 多輪、從冊封根因推、提候選人按才進場、對話不自動改 bedrock。

---

## Phase 4：US4（P2）——按需找佐證

- [X] T014 [P] [US4] 寫佐證紅測：注入假 `app.state.cite_factory` → `POST /chat/cite`（claim）回附引用連結；查無 → 誠實「沒搜到」。
- [X] T015 [US4] 加 `app.state.cite_factory`（預設 `make_web_search` 撒幾個佐證 query）＋`POST /chat/cite`；chat.html「找佐證」接上。跑 T014 轉綠。

**檢查點**：對主張按需找佐證、附引用、查無誠實；不自動每輪搜。

---

## Phase 5：US5＋Polish＋回歸

- [X] T016 [P] [US5] 寫失敗/場空友善紅測：`chat_factory` 拋 `SourceUnavailable`/`OpenAIError` → `POST /chat` 200＋友善、不噴 Traceback；場空（無冊封根因）→ 對話含「場還空」提示。
- [X] T017 [US5] 在 `/chat`、`/chat/cite` 加 `except (SourceUnavailable, OpenAIError)`→`_log.error`＋友善；場空提示。跑 T016 轉綠。
- [X] T018 跑 `uv run pytest tests/unit/test_field_chat.py tests/contract/test_chat_web.py -q` 全綠。
- [X] T019 跑 `uv run pytest -q` 全綠（現 322 + 本增量新測）；確認範圍守住（無自動搜/自動 capture/手機-tunnel/軌跡儀表板/moment A 改動/CLI）。既有路由零回歸。
- [X] T020 **真後端質性驗（SC-006，第一風險）**：重啟 server、`/chat` 對**使用者真實的場**（含 #14/#15）對話一輪 → 檢查回應**從冊封根因往下推、標 grounded/猜、分三層、提可用冊封候選**（呼應 2026-07-29 手動示範）。記錄是否「複刻到讓使用者想餵場」。

---

## 依賴與執行順序
- Foundational（T001–T007）阻塞路由。T004 阻塞 T011；T007（distill/chat backend）供 T012/真後端。
- US1/2/3（T008–T013）：路由＋模板，依 T004/T007。T012 依 `add_why_node`/`anoint`（既有）。
- US4（T014–T015）、US5（T016–T017）依路由就緒。
- Polish/真驗（T018–T020）最後。

## 平行機會
- T001‖T002‖T003‖T005‖T006（不同測案）；T008‖T009‖T010；T014、T016。
- 實作 T004/T007（模組）、T011/T012/T013（app＋模板）、T015/T017（同 app）順序觸同批檔案，序執行。

## MVP
**T001–T013**＝多輪對話、從冊封根因推、反逢迎的膜、提候選人按才進場。US4（佐證）/US5（友善）為邊界，薄。
真驗收（T020／SC-006）＝自動版複刻手動品質到讓使用者想餵場。
