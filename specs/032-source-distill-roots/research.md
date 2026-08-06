# Research：spec 032（源→候選核心理解）

## 決策 1：萃取機制＝rootcause.extract（非 field_chat.distill）
- **選定**：`rootcause.extract.RootCauseExtractor.extract(title, body) -> Candidate`。
- **理由**：它本為「從一則材料抽根因候選」設計，內建 7 條試金石自我反駁＋ladder＋fog_flag＋no_material，正中 FR-002/FR-003（候選須標「AI 推斷、過試金石」）。`field_chat.distill` 吃對話 history、產無試金石的較輕 CandidateDraft，不合。
- **替代**：field_chat.distill（規格輸入原提）——否決：對話導向、無純度守門的試金石。
- **證據**：`src/knowfield/rootcause/extract.py:53-122`（extract 簽章＋StubExtractor＋OpenAIExtractor＋TOUCHSTONES）；`backends/factory.py:33` `make_root_cause_extractor` 已備雙後端。

## 決策 2：源→根因由來＝復用 evidence_urls（零 schema）
- **選定**：整理時把來源 url 存進候選的 `evidence_urls`；讀端 `why_node_source_provenance()` 把「evidence_url 命中現有來源」映成由來連結。
- **理由**：教訓 8「免動既有資料結構，即使略醜」。`why_nodes.evidence_urls` 已存在、`/roots` 已渲染；來源 url 天然就是該候選的「證據＝出處」。連規格假設的「加 nullable 欄」都省了。來源刪除→連結自然消失＝FR-010 優雅。
- **替代**：(a) 加 `why_nodes.source_url` nullable 欄（規格假設）——可行但多一次遷移，非必要；(b) 復用 `conversation_id`——語義錯（來源非對話），否決。
- **證據**：`repository.py:452` add_why_node(evidence_urls…)；`roots.html:82` 已渲染 evidence_urls；`repository.py:642` why_node_provenance（對話由來，另存 conversation_id 側）。

## 決策 3：候選落點＝why_nodes(candidate)，走既有 /roots
- **選定**：`add_why_node`→status='candidate'→`/roots` 審閱→`whynode_anoint` 冊封（全復用）。
- **理由**：純度守衛天然成立——`build_field_system_prompt` 只吃 `list_why_nodes("anointed")`（`app.py:192/414`），候選進不了地基（FR-005/US2）。
- **證據**：`app.py:410` /roots 讀 candidate/anointed；`app.py:422` whynode_anoint；`field_chat.py:80` build_field_system_prompt(roots)。
