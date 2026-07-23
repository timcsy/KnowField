# LearnNews 使用說明（推模式 MVP）

LearnNews 是**分診工具**：把 AI 新聞與論文的洪流去重、依你的興趣排序、濾成「今天
值得點的幾則」，每則附直達原文。深加工（第一性、歸納偏置、外推）由你自己做——
工具只負責把有價值的原礦準確鋪到你面前。

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
| `learnnews interests list\|add <主題>\|remove <主題>\|set <主題...>` | 管理興趣清單（明講優先於學習） |
| `learnnews sources list\|enable <id>\|disable <id>` | 檢視／啟用來源 |

### 拉模式（深挖某主題）

```bash
uv run learnnews pull "latent reasoning" --limit 20   # 預設每則附一句定位
uv run learnnews pull "latent reasoning" --raw        # 純原礦：只給標題＋來源＋連結
uv run learnnews pull --from-digest 3                  # 從最近匯整第 3 則的主題深挖
```

拉是**溯源**：跨來源擴展搜尋該主題（arXiv 用主題查詢、其餘依相關性過濾）、去重、排序、
直達原文；工具只鋪原礦、不下結論（原則 4）。與推（每日分診）互補。

## 設計原則（為什麼這樣做）

- **溯源不代勞**：每則都能直達原文，工具不生成結論式分析（原則 3、4）。
- **興趣過濾**：依你明講的主題過濾排序；行為只做微調，明講永遠可覆寫（憲章原則 VI）。
- **缺漏不靜默**：來源當日取不到時，匯整照常產出並明確標示缺漏（原則 5）。
- **X／Twitter 排除於 MVP**：成本與取得限制，改以論文骨幹＋精選新聞（見 spec）。

詳見 `specs/001-daily-triage-digest/` 的規格與設計文件，以及 `knowledge/` 知識庫。
