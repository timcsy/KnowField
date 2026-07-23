# 004：真實後端改用 OpenAI 格式 API
> 日期：2026-07-23

## 轉移
- 舊（002 計畫時）：真實 embedding 用 sentence-transformers、摘要用 Claude Haiku
  （`anthropic` SDK）。**已被本檔取代。**
- 新：真實 embedding 與摘要**都走使用者的 OpenAI 格式 API**——同一端點的
  `/embeddings` 與 `/chat/completions`。以 stdlib `urllib` 直接呼叫，**零新增相依**；
  實作成既有 `Embedder`／`Summarizer` 可插拔介面的一個後端，離線 stub 仍為預設。

## 為什麼變
使用者手上有 OpenAI 格式 API，不想裝 sentence-transformers（torch，龐大）或
Anthropic SDK。走 OpenAI 格式一次涵蓋 embedding＋chat，且 urllib 直打即可——正好
延續「重量級相依藏在可插拔介面後」的既有教訓（`experience.md`）。金鑰／端點／模型
以 `.env`／環境變數注入（`.env.example` 為範本，`.env` 已 gitignore）。

## 連帶：摘要鷹架修正
真實驗證時發現 chat 模型會把提示的「第一行＝／第二行：」等格式鷹架字面吐進內容。
修法：提示明令「不要加任何標籤／編號」＋解析端 `_clean_line` 剝除前綴（標籤字須接
分隔符才剝，避免誤刪正常句）。教訓見 `experience.md`。

## 影響
- `pyproject.toml` 移除重量級 backends extra（sentence-transformers／anthropic）。
- 新增 `src/learnnews/backends/`（openai_api、factory）、`config.py` 支援 .env。
- 真實驗證：embedding 相關性精準（LLM 推理／RAG／agent 命中）、摘要封頂繁中、
  直達原文、缺漏來源優雅降級。commit `5ea4e0b`、`50205bc`。

## 狀態
✅ 已採用（取代 002 的真實後端計畫）
