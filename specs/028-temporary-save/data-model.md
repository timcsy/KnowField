# Data Model: 對話暫時存檔＋TTL 衰減

## 結構變更：conversations 加 2 欄
- `temporary INTEGER DEFAULT 0`——0＝永久、1＝暫存。
- `last_activity_at TEXT`——最後活動時間（ISO），供 TTL 起算。
- `_migrate` 冪等：`PRAGMA table_info` 無欄則 `ALTER TABLE ADD COLUMN`；**回填**既有列 `temporary=0`（永久）、
  `last_activity_at = created_at`。既有 spec 023 存檔＝永久、不被 TTL 清。**不新增表**。

## 純值（`chat/capture.py`，不落庫）
- `expired_temp_ids(convos, now, ttl_days=7) -> list[int]`：`convos` 每筆含 `id/temporary/last_activity_at`；
  回 `temporary==1 且 now - last_activity_at > ttl_days` 的 ids。parse 失敗/缺時間→保守**不選**（不誤刪）。
- `cheap_title(messages) -> str`：首個 user 訊息截斷（≤20 字），空→「（暫存對話）」。純、不呼 LLM。

## 既有實體（動作對象）
- **對話 Conversation**：加 `temporary`、`last_activity_at`。
  - 暫存：`temporary=1`、便宜標題、逐輪 upsert 同筆、閒置 7 天過期被清。
  - 永久：`temporary=0`、落點標題、無 TTL。

## 生命週期
```
聊天每輪 done → autosave_temporary(temp_id, msgs, now)  [temporary=1, upsert 同筆, last_activity=now]
    │  閒置 >7 天且沒再碰 → 懶清 purge_expired_temporary → 刪
    │  人按「存這段/冊封連同存/轉永久」→ promote_conversation → [temporary=0, 落點標題]  ← 永久、無 TTL
```

## 不變量
- **一段對話一筆暫存**（id-upsert，非每輪新增）。
- **只暫存衰減**：purge 只刪 `temporary=1` 過期者；`temporary=0` 永久零誤刪。
- **升永久不重複**：promote 翻同一筆旗標，不 INSERT 新列。
- **不污染**：暫存與永久皆不進 `build_field_system_prompt`（守衛測）。
- **人閘門**：promote 人觸發；autosave≠承諾（會自己流走）。
