# Research：場對新材料做工（階段 15）

## R1：吸引子對照集＝種子＋已冊封根因
- **決策**：`repository.list_field_attractors() -> list[CorpusEntry]` ＝ `list_seeds()` ＋
  `_anointed_corpus_entries()`（已冊封 why-node，`source_class="root"`、負 entry_id）。**只取冊封的
  吸引子，不含每日流**。
- **理由**：場的「參數」＝人冊封的種子/根因（concept）；每日流是「水」不是吸引子，不該當對照。
  兩者 entry_id 不撞（種子正、root 負）→ `ensure_embeddings` 可共用。

## R2：FieldRelate 流程（單跳 forward pass）
- **決策**：`FieldRelate.relate(title, body) -> FieldRelation`：
  1. `attractors = repo.list_field_attractors()`；空 → `kind="empty"`（提示先冊封）。
  2. **排除材料自己**（若材料就是某種子，用 entry_id/url 排除）。
  3. `ensure_embeddings(attractors)` → vecs；`embedder.embed(title+body)` → mvec；cosine 找最高。
  4. `top_score < min_score`（`rag_min_score`）→ **離所有吸引子都遠** → 材料有實質內容 → `kind="nucleate"`
     （成核候選）；材料太短/空 → `kind="empty"`/提示。
  5. 否則 → `RelationJudge.judge(title, body, top.attractor.claim)` → `kind ∈ {extend, contradict, none}`
     ＋理由；`kind="none"` 也照實回（不硬掰）。回 `FieldRelation(kind, attractor=top, reason, score)`。
- **理由**：MVP 單跳（找最近吸引子）＝夠用且可測；多跳（淺→深路由）列後續。門檻沿用 `rag_min_score`
  的後端尺度校準（教訓 4：離線雜湊帶低、真實嵌入帶高）。

## R3：RelationJudge 可插拔（教訓 1）
- **決策**：`RelationJudge` Protocol `judge(material_title, material_body, attractor_claim) ->
  Relation{kind, reason}`。`StubRelationJudge`（離線確定性：`kind="extend"`、reason「（離線示意）待驗」）；
  `OpenAIRelationJudge`（`_post` chat）。`make_relation_judge(config)`：openai＋key→真實，否則 stub。
- **理由**：離線可測、零外部呼叫（教訓 1）；同 answerer/extractor 的可插拔家族。

## R4：判關係 prompt（grounded、不杜撰、牴觸明確）
- **決策**：system 明令——「只依**這則材料**與**這條根因主張**判定：材料是**延伸**（順著它、補強/推進）、
  **牴觸**（與它相反/反例）、還是**無明顯關聯**。**牴觸要明說**（不含糊）。只用給的兩段內容、
  **嚴禁杜撰**；不確定或無關就回 none。輸出 JSON `{kind, reason}`（reason 繁中一句、指出依據）。」
- **理由**：教訓 7 grounding 落結構；牴觸偵測是殺手級（FR-003）；復用根因萃取的 JSON 解析樣式。

## R5：場不自動改（原則 5）
- **決策**：`FieldRelate` **只回關係、不寫任何庫**（不退根因、不改冊封、不改權重）。牴觸也只顯示。
- **理由**：原則 5／憲章 VI；同根因萃取否決自動冊封——AI 提候選（梯度）、人決定（optimizer step）。

## R6：觸發點與 UI（MVP）
- **決策**：MVP 在 `/library` 每則**種子**加「🧭 關聯到我的場」→ `POST /field/relate`（entry_id）→
  伺服器取該種子 title/body、`relate`（排除自己）→ 小結果頁：關係（延伸/牴觸/無關聯/成核/場空）
  ＋理由＋連到相關根因。匯整條目/搜尋結果的觸發列後續（需暴露條目 id）。
- **理由**：種子有現成 entry_id＋body（library.html 已有）；「我存的這篇跟我的根因怎麼連」是好起點。

## R7：失敗與邊界
- 判關係/嵌入失敗 → `SourceUnavailable`/例外 → 路由攔友善繁中、非 500（教訓 3）。
- 場空 → 友善提示「先冊封根因/種子」。材料太短 → 提示。
- 離線 → stub judge＋HashingEmbedder，零外部呼叫可測。
