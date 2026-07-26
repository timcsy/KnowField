# Contract：場對新材料做工

## `FieldRelate.relate(title, body, exclude_url=None) -> FieldRelation`（`field/relate.py`）
- `repo.list_field_attractors()` 空 → `FieldRelation(kind="empty", reason=提示)`。
- 排除 `exclude_url`（材料自己）。
- 嵌入材料與吸引子、cosine 找最高：
  - `top_score < min_score`（`config.rag_min_score`）→ 材料有實質內容 → `kind="nucleate"`；空/太短 → `empty`。
  - 否則 → `judge.judge(title, body, top.body)` → `kind ∈ {extend,contradict,none}`＋reason；回 `attractor=top`。
- **MUST NOT** 寫任何庫（場不自動改，原則 5）。

## `RelationJudge.judge(material_title, material_body, attractor_claim) -> Relation`
- `StubRelationJudge`：確定性 `{kind:"extend", reason:"（離線示意）待驗"}`；零外部呼叫。
- `OpenAIRelationJudge`：`_post` chat、grounded 判延伸/牴觸/無關聯；解析 JSON；失敗拋 `SourceUnavailable`。
- **MUST** grounded：只依材料＋根因主張；牴觸明說；不確定/無關回 `none`；不杜撰。

## `make_relation_judge(config)`（`backends/factory.py`）
- openai＋key → `OpenAIRelationJudge`，否則 `StubRelationJudge`。

## `repository.list_field_attractors() -> list[CorpusEntry]`
- 種子（`list_seeds`）＋已冊封根因（`_anointed_corpus_entries`）。

## Web
- `POST /field/relate`（`entry_id`＝種子）：取種子 title/body → `relate`（`exclude_url=種子url`）→ 結果頁。
  失敗（`SourceUnavailable`/例外）→ 友善繁中、非 500。
- `GET /field/relate?entry_id=`（或結果頁）：顯示 kind（延伸/牴觸/無關聯/成核/場空）＋reason＋連根因。
- `/library` 種子加「🧭 關聯到我的場」。全繁中。

## 契約測試（離線、零外部呼叫）
1. `FieldRelate.relate`（注入 stub judge＋HashingEmbedder＋含一冊封根因的 repo，材料與該根因相近）
   → `kind` 來自 judge（stub=extend）、`attractor` 為該根因。
2. 材料與所有吸引子都遠（注入 embedder 使 cosine 低）→ `kind="nucleate"`。
3. 場空（repo 無種子無根因）→ `kind="empty"`、不呼叫 judge。
4. 排除自己：材料 url＝某種子 url → 該種子不被選為 attractor。
5. `RelationJudge`：`OpenAIRelationJudge`（注入 poster 回 `{kind:"contradict",reason:...}`）→ 解析對；
   poster 拋 → `SourceUnavailable`；`StubRelationJudge` 回確定性。
6. `list_field_attractors`：只含種子＋已冊封根因（不含每日流條目）。
7. Web：`/library` 種子有「關聯到我的場」；`POST /field/relate`（注入 field_relate_factory 回假
   `FieldRelation`）→ 結果頁顯示關係＋理由；牴觸結果顯示「牴觸」。
8. Web 失敗：factory 拋 → 友善繁中、非 500、不 Traceback。
9. **不改場**：relate 後 `list_why_nodes`/`list_seeds` 不變（無退根因/無改冊封）。
