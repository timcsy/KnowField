# Research: 對話收料的漏

## D1：「同一段」怎麼識別？——內容指紋（非 stable-id）
- **決定**：`conversation_fingerprint(messages)`（訊息序列穩定雜湊）當識別；同指紋＝同段。
- **理由（對地面事實）**：anoint 流每冊封一條就重整頁（`chat_anoint` 回 `messages:[], history_json:"[]"`），
  **client 不持有存檔 id 跨冊封**（chat.html:114 每個候選表單各帶同一份 `history_json`、各自 POST）。故「首次存回 cid、後續帶回」不可行。內容指紋不依賴頁面狀態，且觀測到的 15 份都是**同 32 句**→指紋去重完美命中 1 份。
- **代價**：兩次冊封之間對話又長一句 → 不同指紋、各存一份。實務上批次冊封在同一狀態，可接受，仍遠勝 N 份。
- **spec 影響**：原 Assumption 傾向 stable-id → **已於規劃更正為內容指紋**（憲章 III：實作分歧先改規格）。

## D2：連結存哪邊？——why_node 側加欄（多對一）
- **決定**：加 `why_nodes.conversation_id`（可空）。根因→對話多對一；一份對話可為多條根因由來。
  `why_node_provenance()` 改讀此欄。既有 `conversations.why_node_id` 保留（歷史相容），migrate 回填。
- **理由**：本關係是**多條根因 → 一份對話**（多對一），一個外鍵欄即足；連結表（多對多）是過度設計（YAGNI）。
  存 why_node 側才能讓「同一份對話」被多條根因指到（存 conversation 側的單一 `why_node_id` 表達不了）。
- **駁回**：連結表 `conversation_roots`——多對多我們用不到；徒增 join 與遷移面。

## D3：去重＝冪等 save（幾乎透明）
- **決定**：`save_conversation(title, messages, why_node_id=None)` 改為**指紋冪等**：同指紋已存→回既有 id、
  不插入；否則插入。若給 `why_node_id`，設 `why_nodes[wid].conversation_id = cid`。
- **理由**：anoint 流本就每條呼叫 `save_conversation(title, messages, wid)`；只要它冪等＋連結改邊，**前端零改**
  即修好 #1。附帶：`/chat/save` 連按兩次也不再重複。
- **spec 023 不回歸**：`save_conversation(t,m,wid)`→建對話＋設 `why_nodes[wid].conversation_id`；
  provenance 讀 why_node 側 → `provenance[wid]==cid` 仍成立；刪根因→清該連結、對話仍在（不孤兒）。

## D4：#2 收尾判準——純函式＋client 記上次長度
- **決定**：`distill_gap(total, last_captured, min_total, gap_threshold) -> None | (from, to)`。
  真＝`total>=min_total 且 total-last_captured>=gap_threshold`，區間 `(last_captured+1, total)`。
  chat 頁以 localStorage 記「上次按整理/冊封時的訊息數」當 `last_captured`；無記錄視為 0。
- **理由**：live 對話無逐輪根因對應，最務實訊號＝「自上次收以來又長了多少」。純函式封裝門檻、離線可測、易調。
  不落庫（教訓 8 少動結構）；不自動冊封（原則 5，只算「要不要提醒」）。
- **駁回**：DB 記每輪根因位置——需 turn-tracking、改結構且 live 對話對不上；過重。

## D5：唯讀／人閘門守衛
- 去重只「加連結／回既有 id」，**不刪不改既有存檔**（FR-008）；提醒**不觸發任何寫入**（FR-007）。守衛測釘住。

## 未解問題
- 具體門檻值（min_total／gap_threshold）於實作定，封在純函式與設定一處，可調、有測涵蓋邊界。
