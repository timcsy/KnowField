# 研究：個人內容進料（spec 030）

依據 `draft/2026-08-04-進料轉檔選型.md`（GeneralAffairs 萃取＋2026 SOTA＋Mistral 繁中實測）。

## R1：轉檔器＝Mistral Document AI（經現有 gateway）
- **Decision**：PDF→markdown 走 `azure/mistral-document-ai-2512`，現有 KNOWFIELD gateway `/v1/ocr`、同一把 key、Bearer。
- **Rationale**：實測（英文＋繁中）吐乾淨 markdown、數學保 LaTeX、表格成 md 表、**繁體保留（OCR 讀既有字形，不需 OpenCC）**；零新後端設定、免 GPU（憲章 IV）。
- **Alternatives**：自架 MinerU/olmOCR（要 GPU，砍）；docling 硬相依（重，砍）；vision LLM 逐頁（貴、會幻覺，只當後備）。

## R2：>30 頁對策＝逐頁 render 成圖，不笨切
- **Decision**：超過單份 30 頁上限時，`pdftoppm` 逐頁 render PNG → 每頁 `image_url` OCR → 合併 markdown。
- **Rationale**：實測 Azure 部署單份 30 頁上限（`document_parser_too_many_pages`）；且 poppler `pdfseparate+pdfunite` 笨切會把每頁共用背景圖複製→6MB/49頁膨脹成 45MB。逐頁 render 避開兩者、可控 DPI。
- **Alternatives**：pypdf/pikepdf 共用資源切檔（可行、但多一個相依，先用 render-image 路）；base64 整份（>30 頁被擋）。

## R3：切塊策略＝章節優先＋原子塊不切＋中文字元
- **Decision**：`chunk_markdown`：原子塊（fenced code/`$$`/表格）不切；`^#{1,6} ` 章節為優先切點；章節內 prose 按字元數（~400＋40 重疊）切；短→一塊。
- **Rationale**：「查不到 root cause 多在切塊」（GeneralAffairs f016）；中文無空格→不能 word split（f002 OOM）；公式/表格切半會壞檢索；Mistral 標題階層不穩但編號可靠→用「有標題就切」而非「靠階層深度」。
- **Alternatives**：固定字元窗（會切壞表格/公式，砍）；靠標題階層深度（Mistral 不穩，砍）；語意切塊 LLM（貴、過度擬合，砍）。

## R4：切塊落點＝一來源多筆 digest_entry（不新增表）
- **Decision**：每塊經 `ingest_seed` 存成一筆 `digest_entries`，批次 `ensure_embeddings`。
- **Rationale**：`retrieve_corpus`（029）讀 `digest_entries`→自動可檢索、自動標「你收藏的」、自動不進地基（只讀 anointed why_nodes）。教訓 8 少動結構。
- **Alternatives**：新 chunks 表（違教訓 8，砍）。

## R5：純度守衛天然成立（原則 6）
- **Decision**：收進存 corpus（digest_entries），**永不**寫 why_nodes。
- **Rationale**：`build_field_system_prompt` 只讀 anointed why_nodes→收進內容天然不進地基、不自動變核心理解。延續 spec 029/028/023 守衛。
