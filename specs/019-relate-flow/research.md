# Research：forward-pass 接每日流

無 NEEDS CLARIFICATION——本增量全複用 spec 018，決策已在該規格定案。以下記三個實作抉擇。

## D1：條目 id 如何帶到前端
- **決策**：`DigestEntry` 追加 `entry_id`，`get_last_digest` SELECT `de.id` 填入，`entry_to_page` 用
  `getattr` 帶到 `PageEntry`。
- **理由**：`_entry.html` 為 digest/pull 共用；用 `getattr(entry, "entry_id", None)` 讓 pull 條目自然回 None、
  不顯示鈕（FR-005），無需分模板。尾端加預設欄位不破壞既有具名建構。
- **否決**：改 `Item.id` 塞 digest_entry id——語意混淆（Item.id 是物件 DB id，非匯整條目 id），棄。
- **否決**：另開 API 端點回 id——多一往返、YAGNI，棄。

## D2：路由如何同時吃種子與流
- **決策**：新增 `get_entry_material(entry_id)->(headline_or_title, body, url)|None`，以 `digest_entries.id`
  取任一列；路由用它取代 `list_seeds` 專找種子。
- **理由**：種子與每日流**同住 `digest_entries` 表**（種子在 SEEDS_DATE 容器）——用 id 直取一列即
  可一條路徑服務兩者，library 種子鈕自動續用、零回歸。`FieldRelate` 已支援 `exclude_url` 排除自己。
- **否決**：路由加 `kind` 參數分流種子/流——徒增分支，棄（統一取材料更簡）。

## D3：維持按需，不自動標
- **決策**：每則一個按鈕、使用者點才 POST；首頁載入**不**呼叫任何關聯。
- **理由**：北極星「深淺分明」＋成本（判關係走外部 LLM）。與原則 5（場不自動改）一致——spec 018
  已定調，本增量不破。
