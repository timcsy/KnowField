# LearnNews 使用說明（推模式 MVP）

LearnNews 是**分診工具**：把 AI 新聞與論文的洪流去重、依你的興趣排序、濾成「今天
值得點的幾則」，每則附直達原文。深加工（第一性、歸納偏置、外推）由你自己做——
工具只負責把有價值的原礦準確鋪到你面前。

## Web 介面（階段 6）

```bash
uv sync --extra web            # 裝 fastapi/uvicorn/jinja2
uv run learnnews digest        # 先產一份匯整（首頁會讀它）
# 導覽列：今日匯整 / 主題深挖 / 問答（RAG 可溯源）/ 興趣
uv run uvicorn learnnews.web.app:app --reload   # 開 http://127.0.0.1:8000
```

首頁看今日匯整（散文＋原文圖內嵌＋一鍵原文）、上方輸入框即時「拉」主題、`/interests`
管理興趣。RWD（手機/桌面）、全繁中；後端失敗會顯示友善頁面而非錯誤堆疊。框架相依只在
web 這層，核心仍零相依。

## 安裝（uv）

本專案以 [uv](https://docs.astral.sh/uv/) 管理環境。MVP 核心零外部相依（純標準函式庫）。

```bash
uv sync --extra dev        # 建立 .venv、安裝專案與 pytest
```

真實 embedding／LLM 後端為可選：`uv sync --extra backends`；MVP 預設使用離線的
確定性後端即可運作。

執行測試：`uv run pytest`

## 快速開始

用 `uv run` 執行 CLI（免手動啟用 venv）：

```bash
# 1. 設定你關注的主題（明講清單，主控權在你）
uv run learnnews interests set "LLM 推理" "agent" "編譯器"

# 2. 產出今天的分診匯整
uv run learnnews digest --date 2026-07-23 --limit 15
```

輸出每則含：一句定位、一句為何值得看、直達原文連結。結尾標示缺漏來源與未納入則數。

## 指令

| 指令 | 說明 |
|---|---|
| `learnnews digest [--date D] [--limit N] [--format terminal\|markdown] [--output PATH] [--json]` | 產出當日匯整（推模式：分診） |
| `learnnews pull <主題> [--limit N] [--raw] [--from-digest N] [--format ...] [--json]` | 對主題擴展、去重、溯源（拉模式：深挖） |
| `learnnews ask "<問題>" [--today] [--lang L] [-k N]` | 對已落庫知識庫問答（RAG，可溯源） |
| `learnnews interests list\|add <主題>\|remove <主題>\|set <主題...>` | 管理興趣清單（明講優先於學習） |
| `learnnews sources list\|enable <id>\|disable <id>` | 檢視／啟用來源 |

### 問答（RAG，對累積的匯整發問）

```bash
uv run learnnews ask "最近 agent 記憶體有什麼進展"   # 對所有已落庫匯整檢索、合成可溯源答案
uv run learnnews ask "今天的重點" --today            # 只查最近一份匯整
uv run learnnews ask "RL 新方向" -k 8                 # 取回上限 8 則
uv run learnnews ask "..." --lang English            # 答案語言（預設繁體中文）
```

問答是**個人知識庫**（階段 4 增量 1）：語料＝你跑過的每日匯整；答案**只根據語料、逐點以
`[n]` 標來源**、附原文連結可回溯（原則 3）；**查無相關會明說「沒有相關材料」不杜撰**。
嵌入在產生匯整時一併算好落庫，問答只嵌問題（互動級回應）。未設 API 金鑰時走離線後端
（可跑但語義品質有限）。

### 拉模式（深挖某主題）

```bash
uv run learnnews pull "latent reasoning" --limit 20   # 預設每則附一句定位
uv run learnnews pull "latent reasoning" --raw        # 純原礦：只給標題＋來源＋連結
uv run learnnews pull --from-digest 3                  # 從最近匯整第 3 則的主題深挖
```

拉是**溯源**：跨來源擴展搜尋該主題（arXiv 用主題查詢、其餘依相關性過濾）、去重、排序、
直達原文。與推（每日分診）互補。

### 消化＝可讀散文＋圖（`--format markdown`）

推與拉的每則材料，預設消化成**一篇可讀散文**（完整傳達重點/數據/適用時機），每則一鍵
直達原文。`markdown` 格式可內嵌配圖：

```bash
uv run learnnews digest --format markdown            # 散文消化
uv run learnnews digest --format markdown --ai-image # 無原文圖時允許 AI 示意圖（會標「AI 示意・非原文」）
uv run learnnews digest --raw                        # 純原礦：只標題＋來源＋連結，不生成文字/圖
uv run learnnews digest --lang English               # 指定消化語言（預設繁體中文）
```

消化散文**預設繁體中文**（原文是英文也會翻譯／改寫成繁中）；`--lang` 可指定其他語言。
註：語言由真實後端（OpenAI 格式 API）產生；離線 stub 無法翻譯，會保留原文語言。

原則：消化以省時，但**每則保留一鍵原文**（原則 3/4）；散文忠實原文、不下工具自己的
結論；配圖優先取自原文，AI 圖必明確標示。

## 設計原則（為什麼這樣做）

- **溯源不代勞**：每則都能直達原文，工具不生成結論式分析（原則 3、4）。
- **興趣過濾**：依你明講的主題過濾排序；行為只做微調，明講永遠可覆寫（憲章原則 VI）。
- **缺漏不靜默**：來源當日取不到時，匯整照常產出並明確標示缺漏（原則 5）。
- **X／Twitter 排除於 MVP**：成本與取得限制，改以論文骨幹＋精選新聞（見 spec）。

詳見 `specs/001-daily-triage-digest/` 的規格與設計文件，以及 `knowledge/` 知識庫。
