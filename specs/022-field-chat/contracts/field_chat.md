# 契約：跟你的場聊天（spec 022）

## `ChatBackend.reply(messages: list[dict]) -> str`（新）
- **Stub**（離線）：確定性繁中膜式回應（含「grounded/猜」標記、場-增量段），零外部呼叫。
- **OpenAI**：`_post` chat，messages＝system＋history＋user。`poster` 可注入。失敗拋 `OpenAIError`。

## `build_field_system_prompt(roots: list[WhyNode]) -> str`（新）
膜指引（8 條，見 plan）＋**場脈絡注入**：把每條 anointed root 的 `claim`＋`ladder` 寫進 system，
令回應**從其往下推**。roots 空 → prompt 註明「場還空、標明未接場」。

## `FieldChat.reply(history, user_msg, roots) -> str`（新）
組 messages＝`[system(build_field_system_prompt(roots))] + history + [user(user_msg)]` → `chat_backend.reply`。

## `FieldChat.distill(history, roots) -> CandidateDraft`（新）
結構化提示把對話蒸餾成 `CandidateDraft(claim, ladder, evidence_urls)`（供人審＋編輯）。

---

# 契約：web 路由（spec 022）

## `GET /chat`（新）
對話頁：空對話＋場摘要（已冊封 N 條根因）。桌面友善。

## `POST /chat`（新）
- **輸入**：`history`（hidden JSON）＋`message`。
- **行為**：append user → `app.state.chat_factory(history, message)`（預設 `FieldChat.reply` with
  `list_why_nodes('anointed')`）→ append assistant → 重繪對話＋更新 hidden history。
- 失敗（`SourceUnavailable`/`OpenAIError`）→ `_log.error`＋友善（教訓 3）。

## `POST /chat/distill`（新）
history → `app.state.distill_factory(history)`（`FieldChat.distill`）→ 可編輯冊封候選表單（claim/ladder/urls）。

## `POST /chat/anoint`（新，人閘門）
- **輸入**：`claim`、`ladder`（多行）、`evidence_urls`（多行，可空）。
- **行為**：`repo.add_why_node(claim, urls, [], False, 0, today, ladder)`+`repo.anoint_why_node(id)` → 確認訊息（可回 `/roots` 檢視/刪）。
- **原則 5**：唯有此路由（人按）寫 bedrock；`GET/POST /chat` 永不寫。

## `POST /chat/cite`（新，按需）
- **輸入**：`claim`。
- **行為**：`app.state.cite_factory(claim)`（`make_web_search` 撒幾個佐證 query）→ 回附引用連結；查無誠實說沒搜到、不杜撰。

## `chat.html`＋`base.html`
- 對話串（user/assistant 泡泡）＋hidden history＋輸入框；每則 assistant 下可「找佐證」；對話下方「整理成冊封候選」→ 候選表單含「冊封」。導覽加「跟場聊」。
