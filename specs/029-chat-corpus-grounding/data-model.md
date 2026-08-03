# Data Model: 問答併進聊天

**無結構變更**——只讀既有 `corpus`／`entry_embeddings`；不新增表/欄。

## 純函式／衍生
- `retrieve_corpus(repo, embedder, query, top_k, min_score) -> list[CorpusEntry]`（rag/service.py）：
  找相關收進條目（cosine ≥ min_score，加權排序，取 top_k）。空語料/無相關→`[]`。
- `corpus_contents`：注入 field-chat 的證言塊資料——`[{"n","title","excerpt"}]`（由 hits 組出，唯讀）。

## 既有實體（動作對象）
- **核心理解（root / WhyNode）**：地基。`build_field_system_prompt(roots)` 的**唯一**來源（收進不得入）。
- **收進條目（CorpusEntry）**：既有（title/url/material/source_class＋embedding）。本功能**檢索、當證言注入**，唯讀。
- **來源（Source）**：答案引用項。本功能加 `kind`（`web`/`corpus`）；`corpus` 顯示「你收藏的」。

## 不變量
- **收進＝證言非地基**：`corpus_contents` 只進獨立注入塊，**絕不進** `build_field_system_prompt`。
- **不自動變核心理解**：聊天引用收進**不呼叫** add_why_node；`/核心理解` 不因引用而增。
- **cited-only**：只有被答案 `[n]` 引用的來源（web 或收進）才列。
- **best-effort**：檢索失敗/無語料→聊天照跑（只 核心理解＋web）。
- **腦力激盪**：不撒網、不檢索收進（沙盒）。
