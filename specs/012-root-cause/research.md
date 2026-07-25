# Research：根因萃取（階段 10）

## R1：why-node 存哪、避免與種子混淆
- **決策**：新 `why_nodes` 表（不塞進 digest_entries）。欄位：`id`、`claim`、`evidence_urls`(JSON)、
  `touchstones`(JSON)、`fog_flag`(int)、`status`('candidate'|'anointed')、`source_entry_id`(來源種子)、
  `created_at`。`CREATE TABLE IF NOT EXISTS`＋`_migrate` 冪等（教訓 8：新表 OK、不動既有表）。
- **理由**：why-node 是 genuinely 新資料、語義與載體（種子）不同（concept：吸引子是根因不是文件）。

## R2：已冊封 why-node 餵回 ask——負 entry_id 避碰撞
- **決策**：`list_corpus_entries` 在既有 digest_entries 查詢後 **UNION** `status='anointed'` 的 why-node，
  映成 `CorpusEntry(entry_id = -why_node.id, title="根因：{claim前段}", url=首個 evidence, body=claim,
  source_class="root")`。**用負 id** 讓 why-node 與 digest_entries（正 id）在 `entry_embeddings`
  （PK (entry_id,tag)、無 FK）不碰撞。
- **理由**：復用整條檢索/嵌入路徑（`ensure_embeddings` 照嵌 body=claim、存負 id），零改既有表；
  刪 why-node 時一併清 `entry_embeddings WHERE entry_id = -id`（比照 delete_seed）。
- **候選不進 corpus**：只有 `anointed` UNION 進來——候選未冊封不影響問答（原則 5）。

## R3：root 權重（重吸引子）
- **決策**：`RagService._weight` 加 `root` 層：`root→rag_root_weight（預設 2.0）`、`explainer→1.5`、
  其餘 1.0。門檻仍用原始 cosine 把關（權重只排序入選者，沿用 spec 006 R5）。
- **理由**：concept「一篇講透的解說文打敗五十篇；根因是 why 濃度最高的重吸引子」→ root > explainer。

## R4：RootCauseExtractor 介面與試金石
- **決策**：`extract(title, body) -> Candidate`；`Candidate{claim:str, touchstones:list[{name,passed:bool}],
  fog_flag:bool, evidence:list[str], no_material:bool}`。7 條試金石固定名單。
  - `StubExtractor`（離線確定性）：claim＝「（離線示意）根因待驗」、touchstones 全 `passed=False`
    （標「待驗」）、`no_material=False`。零外部呼叫。
  - `OpenAIExtractor`：`_post` chat，system 明令「抽為何 work 的根因、**對自己逐條試金石反駁**、
    標 pass/fail、標霧詞、**只用材料內容不杜撰**、抽不出就說沒把握」；輸出要求 JSON（claim／
    touchstones／fog_flag／no_material），解析；解析/呼叫失敗 → 拋 `SourceUnavailable`（路由攔）。
- **理由**：試金石逐條是 concept 強制的 folie à deux 解藥（對自己 adversarial、不只證實）。

## R5：grounding 落結構（教訓 7）
- **決策**：候選**必帶** `evidence`（來源種子 url）＋ `touchstones`；repository 存候選時，evidence 為空
  → 不建候選（或標不可冊封）。web **冊封動作**僅在候選有證據＋試金石時提供。`no_material=True` 的
  萃取回應 → 不建候選、頁面友善提示「這則抽不出有把握的根因」。
- **理由**：標示與證據由程式保證，不靠提示自律（比照 AI 圖標籤、RAG 無材料先例）。

## R6：冊封／退回（人 optimizer step）
- **決策**：web `/whynode/anoint`（entry：why_node id＋可編輯 claim → status='anointed'）、
  `/whynode/remove`（刪）。**無自動轉正路徑**（原則 5、concept :126 否決自動冊封）。沿用 `/library`
  的 POST→RedirectResponse 樣式。
- **理由**：冊封是人不可逆語義動作（拆開的 optimizer：人＝optimizer step）。

## R7：UI 放哪
- **決策**：`/library` 每則種子加「萃取根因」鈕（POST `/whynode/extract`，entry_id=種子）；萃取後
  導到 `/roots`（新頁）顯示**候選**（claim＋試金石逐條 badge＋霧詞旗標＋證據連結＋冊封/退回）與
  **已冊封**清單。
- **理由**：萃取源頭在種子（library），根因管理自成一頁（roots）＝場的「吸引子」檢視。

## R8：失敗與邊界
- 萃取失敗/逾時/無金鑰 → `SourceUnavailable` → 路由友善繁中、頁面不崩（教訓 3）。
- 同種子重複萃取 → 產生新候選（不覆蓋已冊封）。
- 離線 stub → 確定性候選、試金石全「待驗」，契約測試零外部呼叫。
- 已冊封被退回 → 刪 why-node＋清其負 id 嵌入 → ask 不再檢索到。
