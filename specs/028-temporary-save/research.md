# Research: 對話暫時存檔＋TTL 衰減

## D1：暫存 upsert（id）≠ 永久存（fingerprint dedup）
- **決定**：暫存用 **client 持 `temp_id` 的 id-upsert**（一段對話一筆、逐輪更新）；永久手動存維持 spec 025 的
  **內容指紋 dedup**（temporary=0）。
- **理由**：spec 025 的 dedup 靠內容指紋——但暫存**每輪內容都變**、指紋每輪不同，用指紋會**每輪新增一筆＝囤積**，
  正是本 spec 要防的。id-upsert 才能「一段對話一筆」。
- **temp_id 從哪來**：首次 autosave INSERT 回傳 id → client 記在 hidden 欄＋localStorage（跨重整）；後續 autosave 帶回更新同筆。

## D2：升永久＝promote 同一筆
- **決定**：`promote_conversation(cid, 落點標題, why_node_id=None)` 翻 `temporary=0`＋設標題（＋連根因）。
  client 把 `temp_id` 帶進「存這段/冊封連同存/轉永久」→ promote 該筆；**無 temp_id → 退回 `save_conversation`（建永久）**。
- **理由**：暫存已是那筆對話，升永久只是改生命週期旗標＝**不新增重複**（呼應 025/026 的反囤積）。落點標題沿用 spec 027（升永久才生、省成本）。

## D3：TTL 純函式＋懶清、不開背景
- **決定**：`expired_temp_ids(convos, now, ttl_days=7)`（純：parse `last_activity_at`、`now - last_activity > ttl 且 temporary`）。
  `purge_expired_temporary(now)` 在**載 `/conversations` 或存檔**時跑。**不開背景/定期排程**。
- **理由**：單使用者本機，懶清足夠且零基礎設施（教訓 8 精神：能不加就不加）。純函式離線可窮舉測（過期/未過期/邊界/永久不選/計時重設）。
- **計時重設**：新對話/接回 → 更新 `last_activity_at`（autosave 每輪更新即達成；接回另 `touch`）。

## D4：暫存便宜標題（不每輪呼 LLM）
- **決定**：暫存標題＝`cheap_title(messages)`（首個 user 訊息截斷，純函式）；升永久時才 `title_factory`（spec 027 落點標題）。
- **理由**：每輪 autosave 若呼 LLM 生標題＝貴又慢。暫存只需一眼可認；正式落點標題留給「決定長留」那一刻。

## D5：暫存仍沙盒——不注入回場（原則 6）
- **決定**：暫存與永久一樣**不進 `build_field_system_prompt`**（場脈絡只來自冊封根因）。守衛測：存含 SECRET_FANTASY 的
  **暫存**後，新 `/chat` 的 system prompt 不含它（比照 spec 023）。
- **理由**：暫存是沙盒短期，發想/幻想更不該回灌。＝原則 6 純度延伸到暫存層。

## 未解問題
- 無。TTL=7 天使用者定。欄名/觸發點於實作定。
