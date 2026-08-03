# Contracts: 問答併進聊天

## A. 檢索純函式（`src/learnnews/rag/service.py`）

### `retrieve_corpus(repo, embedder, query, top_k, min_score) -> list[CorpusEntry]`
- `list_corpus_entries`→`ensure_embeddings`→`embed(query)`→`cosine`→`≥ min_score` 過濾→加權排序→`top_k`。
- 空語料/無相關 → `[]`。離線可測（注入 stub embedder）。純檢索、**不合成**。
- `RagService.answer` 改呼叫它（行為不變、既有測不回歸）。

## B. field-chat 注入（`src/learnnews/chat/field_chat.py`）

### `_messages(..., corpus_contents=None)`（改）／`reply`/`reply_stream` 透傳
- `corpus_contents`＝`[{"n","title","excerpt"}]` → 注入**獨立 system 塊**：
  「你收藏的資料（外部證言——可引用、但比你精選的核心理解軟、可能他人觀點或有誤，別當自己的地基）：\n[n] title — excerpt」。
- **不碰 `build_field_system_prompt`**（只吃 roots）。
- `_MEMBRANE` 加一句三層：核心理解＝地基／你收藏的＝證言／web＝外部。

## C. Web（`src/learnnews/web/app.py`＋模板）
- `_default_chat`／`chat_stream`：非腦力激盪時，web 撒網後也 `retrieve_corpus`（best-effort；可注入 `corpus_search_for_test`）。
  把收進 hits 與 web 來源**併成一個 sources 清單**（連號、帶 `kind`）＋組 `corpus_contents` 傳給 `fc.reply(...)`。
  cited-only：只留被答案 `[n]` 引用的來源。
- `/ask` → `RedirectResponse('/chat', 302)`；`base.html` 導覽移除「問答」；`ask.html` 退場。
- `chat.html`：來源列依 `kind` 顯示——`corpus`→「📎 你收藏的」小標、`web`→原樣。

## D. 測試契約
- **單元**（`test_corpus_retrieve.py`）：`retrieve_corpus`——相關命中、門檻過濾、空語料→[]、注入 stub embedder；
  field-chat：`corpus_contents` 進獨立塊、且 `build_field_system_prompt(roots)` **不含**收進內容。
- **web**（`test_chat_corpus_web.py`）：
  - 注入 corpus_search＋含 `[n]` 的 stub 回答 → 答案來源含收進條目（標 `kind=corpus`、cited-only）。
  - **純度守衛**：種含 `SECRET_外部觀點` 的收進 → 聊天後 `build_field_system_prompt(anointed)` 不含它；`list_why_nodes` 不因引用而增。
  - 無收進/檢索失敗 → 聊天照跑（只 核心理解＋web）、不 500。
  - `/ask` → 302 導向 `/chat`；導覽無「問答」。
