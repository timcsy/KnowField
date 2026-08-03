# Implementation Plan: 問答併進聊天——聊天 ground 在核心理解＋收進的文章＋web

**Branch**: `029-chat-corpus-grounding` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/029-chat-corpus-grounding/spec.md`

## Summary

抽出 RAG 的**檢索段**成純函式 `retrieve_corpus(repo, embedder, query, top_k, min_score)->list[CorpusEntry]`（RagService.answer 改呼叫它、行為不變）。聊天每輪（非腦力激盪）除 web 撒網，也**檢索相關收進條目**，把它們**當「你收藏的」證言注入 field-chat 場脈絡**（比照既有 `url_contents` 注入塊）＋併入 `sources`（帶 `kind` 標記）。**膜分層**：`build_field_system_prompt` **只含核心理解＝地基（天然守純度）**；收進走**獨立注入塊**、提示明令「證言、比核心理解軟、絕不當地基」。`/ask` 導向 `/chat`、導覽「問答」退場。

## Technical Context

**Language/Version**: Python 3.12+（uv）
**Primary Dependencies**: 既有 FastAPI＋Jinja2；檢索**複用既有 embeddings/ranking**（零新第三方相依）
**Storage**: SQLite——**只讀** `corpus`／`entry_embeddings`；**不新增表**（教訓 8）
**Testing**: pytest（現 265 綠）
**Target Platform**: 本機 web（單使用者）
**Project Type**: web（FastAPI＋Jinja2）
**Performance Goals**: 每輪多一次 embedding 檢索（本地 cosine，便宜）；人感即時
**Constraints**: 原則 6（收進＝證言非地基，守衛測）、best-effort（教訓 3）、離線可注入測（教訓 1）、全繁中、核心零相依
**Scale/Scope**: 個人語料；抽 1 檢索純函式＋field_chat 加 1 注入參數＋app 2 chat 路徑接檢索＋來源標記＋/ask 退場

## Constitution Check

*GATE：Phase 0 前必過；Phase 1 後複查。*

- **I. TDD** ✅ `retrieve_corpus` 先紅後綠（相關/門檻/空）；field_chat 注入＋純度守衛測（收進不進 build_field_system_prompt）；web 端引用/標記/best-effort/fallback 測。
- **II. 繁中** ✅ 全繁中。
- **III. 規格驅動** ✅ 可追溯 FR-001…009。
- **IV. YAGNI** ✅ 複用 RAG 檢索、embeddings；**無新表**；收進走既有 `url_contents` 注入模式，不發明新機制。
- **V. 可觀測性／錯誤** ✅ 檢索失敗/無語料→聊天照跑（教訓 3）；只列被引用的（cited-only）。
- **VI. 決策主權／原則 6** ✅ **收進＝證言非地基**：`build_field_system_prompt` 只含核心理解，收進走獨立注入塊，**絕不當地基、不自動變核心理解**（守衛測）。

**結論：無違憲。守純度天然落地——地基（system prompt）只吃 roots，收進與 `url_contents`/web 同層，是「外部證言」不是「你的理解」。**

## 關鍵設計決策（詳見 research.md）

1. **抽檢索段、與合成解耦**：`retrieve_corpus` 只做「找相關收進條目」（回 CorpusEntry hits），**不合成**。RagService.answer
   改呼叫它（行為不變，測試不回歸）；聊天拿 hits **自己**用 field-chat 合成（帶膜），不走 RAG 的 answerer。
2. **收進當「證言」注入，比照 `url_contents`**：`_messages` 加 `corpus_contents` 參數→注入獨立 system 塊
   「你收藏的資料（外部證言，可引用、比核心理解軟、可能他人觀點/有誤，別當地基）：[n] title — 摘錄」。
   **關鍵：不碰 `build_field_system_prompt`（只含 roots）→ 純度天然守住。**
3. **統一來源編號＋標記**：web 與收進併成一個 `sources` 清單、跨兩者 `[n]` 連號、每項帶 `kind`（`web`/`corpus`）；
   cited-only 濾（只列被答案引用的）。chat.html 來源渲染依 `kind` 顯示「你收藏的」標記。
4. **膜提示分層**：`_MEMBRANE` 加一句三層（核心理解＝地基 / 你收藏的＝證言 / web＝外部）；收進注入塊 header 再強調。
5. **/ask 退場**：`/ask` route → 302 導向 `/chat`；導覽移除「問答」；RagService/檢索**保留**（聊天在用）。ask.html 與其
   web 測退場（檢索能力改由 chat 測涵蓋）。

## Project Structure

### Documentation (this feature)
```text
specs/029-chat-corpus-grounding/
├── plan.md · research.md · data-model.md · quickstart.md
├── contracts/chat-corpus.md
└── tasks.md（/speckit-tasks 產出）
```

### Source Code (repository root)
```text
src/learnnews/
├── rag/
│   └── service.py              # 【改】抽出 retrieve_corpus(repo, embedder, query, top_k, min_score)；answer() 改呼叫它
├── chat/
│   └── field_chat.py           # 【改】_messages/reply/reply_stream 加 corpus_contents 注入塊；_MEMBRANE 加三層一句
└── web/
    ├── app.py                  # 【改】_default_chat＋chat_stream：web 撒網後也檢索收進(best-effort、可注入 corpus_search_for_test)、
    │                           #   併入 sources(kind)＋corpus_contents；/ask→導向 /chat
    └── templates/
        ├── base.html           # 【改】導覽移除「問答」
        └── chat.html           # 【改】來源渲染依 kind 顯示「你收藏的」標記

tests/unit/
├── test_corpus_retrieve.py     # 【新】retrieve_corpus（相關/門檻/空語料/注入 stub embedder）
└── test_chat_corpus_web.py     # 【新】聊天引用收進(附 [n]、標你收藏的)／膜分層＋純度守衛(收進不進 build_field_system_prompt、不自動變核心理解)／檢索失敗 fallback／cited-only／/ask 導向
```

**Structure Decision**: 沿用單一 web 專案。檢索抽成 rag 內純函式（DRY，RAG 與 chat 共用）；field_chat 加一個注入參數（沿用 url_contents 模式）；app 兩條 chat 路徑接檢索。無新表、無新相依。

## Complexity Tracking

> 無違憲項。收進注入沿用既有 `url_contents` 模式、檢索複用既有 RAG——降重複、非增複雜度。
