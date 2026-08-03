# Research: 問答併進聊天

## D1：抽檢索段、與合成解耦
- **決定**：把 RagService.answer 的檢索段抽成 `retrieve_corpus(repo, embedder, query, top_k, min_score) -> list[CorpusEntry]`
  （list_corpus_entries→ensure_embeddings→embed(query)→cosine→門檻過濾→加權排序→top_k）。RagService.answer 改呼叫它。
- **理由**：聊天要的是**相關條目**，不是 RAG 的合成答案（聊天用 field-chat 帶膜自己合成）。抽出來＝DRY、
  兩邊共用同一檢索、離線可測（stub embedder）；RagService.answer 行為不變→既有測試不回歸。

## D2：收進當「證言」注入、比照 url_contents
- **決定**：`field_chat._messages` 加 `corpus_contents` 參數，注入**獨立 system 塊**：
  「你收藏的資料（外部證言——可引用、但比你精選的核心理解軟、可能是他人觀點或有誤，別當自己的地基）：
  [n] {title} — {摘錄}」。`reply`/`reply_stream` 透傳。
- **理由**：收進的是**別人的內容**，性質＝外部證言，跟「使用者貼的網址內容」同層——直接沿用既有 `url_contents`
  注入模式，不發明新機制。**關鍵：走注入塊、不碰 `build_field_system_prompt`（只吃 roots）→ 純度天然守住（D5）。**

## D3：統一來源編號＋kind 標記
- **決定**：web 撒到的來源與收進 hits **併成一個 sources 清單**、跨兩者 `[n]` 連號、每項帶 `kind`（`web`/`corpus`）。
  答案的 `[n]` 引用照舊；cited-only 濾（只列被引用的）。chat.html 來源列依 `kind` 顯示「你收藏的」小標。
- **理由**：模型看到的是一組編號來源，`[n]` 一致；kind 讓使用者一眼分「你收藏的 vs web」。沿用既有 cited-only 慣例。

## D4：膜提示分層（三層）
- **決定**：`_MEMBRANE` 加一句：**核心理解＝你的地基（往下推）／你收藏的資料＝外部證言（引用、比核心理解軟）／
  web＝外部**；收進注入塊 header 再強調「別當地基」。
- **理由**：這是這功能的靈魂——讓模型**引用**收進資料、但**不把它當成你的理解**。提示分層＋注入分塊雙保險。

## D5：純度守門（原則 6，最硬）——天然落地
- **事實**：`build_field_system_prompt(roots)` **只吃 roots**。收進走 `corpus_contents` 獨立注入塊、**不經** build_field_system_prompt。
- **決定**：守衛測——存一則含 `SECRET_外部觀點` 的收進 → 聊天後 `build_field_system_prompt(roots)` **不含**它；
  且聊天**不呼叫 add_why_node**（收進不自動變核心理解）。比照 spec 023/028 的不注入回場守衛。
- **理由**：地基與證言分塊，是原則 6「複利而不污染」在「別人的內容」上的落實——引用可以、當地基不行。

## D6：/ask 退場、檢索保留
- **決定**：`/ask` route → 302 導向 `/chat`；導覽移除「問答」；`ask.html` 與 /ask 的 web 測退場。
  RagService＋`retrieve_corpus`＋embeddings **保留**（聊天在用；RagService.answer 的檢索測仍涵蓋 retrieve_corpus）。
- **理由**：能力已在聊天；收斂入口（延續砍鷹架「一個對話入口」）。檢索是共用資產，留著。

## 未解問題
- 收進注入的「摘錄」長度／top_k／門檻沿用既有 RAG 尺度（rag_top_k/rag_min_score），先不另調；封在 retrieve_corpus 參數、易調。
