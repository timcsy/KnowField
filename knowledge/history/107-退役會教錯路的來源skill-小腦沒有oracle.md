# 107：退役 `evaluate-and-add-source`——小腦記著一條不存在的路

> 日期：2026-08-23。**決策轉移（退役）**。承 [068](068-退役新聞分診子系統.md)（分診退役）。
> 由 `/knowie-next` 對**正式庫**跑審計時照出。

## 轉移

- **舊**：`knowledge/skills/evaluate-and-add-source/` ——
  「為 KnowField 評估並加入一個新的新聞/論文來源：實測 → 挑 → **加進 `DEFAULT_SOURCES`** →
  **跑 digest 驗證供料** → 反流」。已投影到 `.claude/skills` 與 `.agents/skills`。
- **新**：**退役**。它教的第 3–5 步指向一條**不存在**的路。

## 證據（逐條查過）

| 查什麼 | 結果 |
|---|---|
| skill 第 4 步要跑的 `knowfield … digest --limit 6` | ⚠️ **`digest` 子指令不存在**——`cli/__main__.py` 只註冊了 `ask`（:20）與 `ingest`（:28） |
| 誰寫 `sources.last_fetch_at` | 只有 `models/__init__.py:30` 定義，**零處寫入** |
| 誰讀 `sources` 表 | 只有 `app.py:85`（空庫自動塞 `DEFAULT_SOURCES`）與 `:925`（刪除） |
| `build_adapters` 誰呼叫 | **只有 `tests/unit/test_build_adapters_web.py`** |
| 前端 `/sources` 顯示什麼 | `pages.library()` ＝收進的來源群組，**不是 `sources` 表** |

正式庫的審計數字：**15 個訂閱、0 個供過料（0%）**。那 15 筆不是使用者訂的，是空庫時程式自動塞的。

⇒ 拉模式（訂閱＋定時抓）隨 [068](068-退役新聞分診子系統.md) 一起退役了，
現在的進料是**四張嘴**（貼上／URL／PDF／YouTube）。skill 停在退役前的世界。

## ⚠️ 為什麼這比死程式碼糟

knowie core 自己寫著：

> skill ＝ 知識，只是使用意圖是「執行」；高 stakes（會 acts、**可能靜默作惡**）

死程式碼靜靜躺著；**壞掉的 skill 會被照著做**。而且它已經投影到兩個 skillDirs，
**Codex／Gemini 也看得到它**——下一個照著跑的未必是我。

而它壞了三週沒人發現，因為 **skill 沒有 oracle**：不進 CI、沒人跑、沒有測試。
這正是 `experience.md`「判一份知識死沒死，看『如果它錯了，誰會發現』」落在小腦上的樣子。

## 為什麼是退役而不是改寫

它的**前提**沒了（一份會被定時抓取的來源名冊），不只是步驟過期。
留一個改寫過的空殼，等於保留一個沒有消費者的東西——正是這次審計要抓的那類。

**判準保留在這裡**（它們是知識，不是可執行物）：

- **訊噪比 > 量**：AI 專門策展電子報（Import AI、Last Week in AI）、官方部落格、
  品質新聞（Ars Technica AI）優先；通用搜尋（Google News）雜訊多，**避免**。
- **免金鑰、法遵**：公開頁／官方 feed；尊重 robots/ToS。
  ⚠️ **Semantic Scholar free search 持續 429，別當預設**（見 [005](005-來源名冊盤點.md)）。
- 實測手法（stdlib 探端點、數 `<item>`／`<entry>`）：`git show` 這一版的 SKILL.md 可取回。

## 順帶修掉的一個假訊號

`audit-field-usage` 把「來源訂閱」列成**現役功能**，於是報告永遠有一個 🔴。
既然沒有任何抓取路徑，那個 🔴 是**工具在說謊**，不是功能沒人用。
⇒ 比照「每日匯整（已退役）」那一列，改標為殘骸存量。

## 未決（留給人裁決，audit 紀律 3：輸出不授權砍）

1. 要不要停掉「空庫自動塞 15 個源」（製造沒有消費者）
2. `cli/fetchers.py`／`DEFAULT_SOURCES`／`sources` 表的去留（動它要連 `test_build_adapters_web.py` 一起）
3. **「現在怎麼跟上趨勢」** ——根公理還在，機制換了。這是設計題，該進 `draft/`，不是清理題。

## 相關

- [068](068-退役新聞分診子系統.md)——把這條路退役掉的那次。
- [005](005-來源名冊盤點.md)、[006](006-精選新聞源取代-Google-News.md)、[007](007-加日更產業新聞源.md)——這個 skill 當初固化的那三次重複。
