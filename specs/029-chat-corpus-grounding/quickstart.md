# Quickstart: 問答併進聊天

## 前置
- 在 `029-chat-corpus-grounding`；`uv run pytest -q` 現 265 綠。
- 只讀既有語料/embeddings，無 migration。

## 跑測試（TDD）
```bash
uv run pytest tests/unit/test_corpus_retrieve.py tests/unit/test_chat_corpus_web.py -q
uv run pytest -q     # 全套不回歸（265 →）
```

## 手動驗證（web，真實 knowfield.db）
```bash
KNOWFIELD_DB=knowfield.db uv run uvicorn knowfield.web.app:create_app --factory --port 8000
```
1. **收進幾篇**：到「收進」貼幾個相關 url（或已收過）。
2. **聊天引用**：到「跟知識聊」問相關問題 → 答案的來源清單應含**你收進的那幾篇**（標「📎 你收藏的」、附 [n]），
   跟 web 來源分得清。
3. **膜分層**：答案把你收的資料當「你收的資料說…」的證言、把你精選的核心理解當地基往下推。
4. **純度**：到「核心理解」頁確認**沒有**因為聊天引用收進而多出核心理解（收進不自動變地基）。
5. **fallback**：沒收進任何東西時，聊天照常（只 核心理解＋web）。
6. **問答退場**：導覽沒有「問答」；舊 `/ask` 網址導向聊天。

## 驗收對照（spec SC）
- SC-001：聊天引用相關收進（[n]、你收藏的）；無關/無收進不硬塞。
- SC-002：膜分層＋守衛測（收進不進地基 system prompt、不自動變核心理解）。
- SC-003：檢索可注入、離線可測；失敗/無語料→照跑。
- SC-004：cited-only。
- SC-005：/ask 退場、能力在聊天。
- SC-006：全繁中、核心零相依、無新表、265 不回歸＋新測。
