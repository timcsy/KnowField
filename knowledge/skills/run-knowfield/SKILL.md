---
name: run-knowfield
description: 在本機把 KnowField 前後端跑起來、開到指定頁面用眼睛看。當要驗證一個改動在真實畫面上長什麼樣、或做「真驗收（超越測試綠）」時使用——測試綠只證明你想到的都對了，證明不了你沒想到的。
---

# 跑起來看（KnowField 本機）

**為什麼存在**：2026-08-18，spec 037 出貨時 **420 個測試全綠**，把 app 真的開起來之後
**兩眼之內照出兩個缺陷**——標題沒被轉換（沒人想到要斷言）、按鈕叫「看原文」與頁面既有的
「原文＝原站／PDF」撞名（使用者一眼看出）。兩個都不是測試形態抓得到的。

而 `vision.md` 的階段 16 有一條掛了三週的未完項「真驗收（超越測試綠）」——這個 skill 是它的
**當下面**器官；累積面那半是 [`audit-field-usage`](../audit-field-usage/SKILL.md)。

啟動方法在此之前**沒有記錄在任何找得到的地方**（root 無 README、`AGENTS.md` 沒寫、
`deploy/` 只有 helm），唯一一條埋在 `history/074` 一篇講改名的條目裡，而且只有後端。
至少已經重新摸索過四次。

## 判準：跑起來是為了**看**，不是為了證明它起得來

服務起來、回 200，只證明入口點解析得了。那不叫跑起來看。**開到你剛改的那一頁，
用眼睛看那個東西**——沒有這一步，這個 skill 沒有存在的理由。

## 步驟

### 1. 起後端

```bash
KNOWFIELD_AUTH_DISABLED=1 uv run uvicorn 'knowfield.web.app:create_app' --port 8000
```

⚠️ **`KNOWFIELD_AUTH_DISABLED=1` 是這裡唯一的必要魔法**。`.env` 裡有 allowlist ＋ Google
client id/secret，`auth_active()`（`src/knowfield/web/auth.py:25`）就會啟用門鎖，本機直接開會被
擋在登入頁。這個旗標是 `config.py:40` 就備好的 dev bypass（註解：「防設錯鎖死自己」）。
**只給本機，正式環境勿設。**

（`--factory` 不需要，uvicorn 會自動偵測 `create_app`。）

### 2. 起前端

```bash
cd frontend && npm run dev
```

⚠️ **讀它印出來的 port，別假設 5173**。5173 被佔時 vite 會自動跳 5174/5175，網址要跟著改：

```
➜  Local:   http://localhost:5174/
```

前端會把 `/api` proxy 到 `127.0.0.1:8000`（`vite.config.ts:52`），所以後端一定要先起。

### 3. 開到你要看的那一頁

| 要看什麼 | 路徑 |
|---|---|
| 某一份來源 | `/source?u=<url-encoded>` |
| 對話 | `/conversations`、`/conversations/:id` |
| 核心理解 | `/roots` |
| 文章 | `/articles`、`/articles/:id` |

來源的 `u` 要 URL 編碼（`paste:abc` → `paste%3Aabc`）。查有哪些來源：

```bash
curl -s localhost:8000/api/library | python3 -m json.tool | head -40
```

### 4. ⚠️ 改了後端程式碼之後**必須重啟**

上面的指令沒有 `--reload`。改完 `src/` 不重啟，你看到的是舊畫面——
**而你會以為改動沒生效，然後去改對的東西**（這正是 experience「驗證管線與正式路徑不同就是在量別的東西」
的變體）。

```bash
pkill -f "uvicorn knowfield.web.app"   # 然後重跑步驟 1，並確認舊 process 真的沒了：
ps aux | grep -c "[u]vicorn knowfield.web.app"      # 應為 0
```

前端不用：vite 會熱更新。

⚠️⚠️ **殺完要確認真的殺掉了**。啟動時寫成 `uvicorn 'knowfield.web.app:create_app'`（帶引號）
但 shell 會把引號吃掉，process 命令列裡**沒有**引號——所以 `pkill -f "uvicorn 'knowfield..."`
永遠匹配不到。舊 server 繼續佔著 8000，新的起不來就默默退出，**而你以為你在看新版**。
這個坑在本 skill 第一版的指令裡真的發生過：驗證出來的結果全是舊碼跑的。
`ps aux | grep -c "[u]vicorn knowfield.web.app"` 要是 0 才算殺乾淨。

### 5. 收工

```bash
pkill -f "uvicorn knowfield.web.app"
pkill -f "vite"
```

### ⚠️ 公式多的頁面截圖會逾時

MathJax 排版很吃 CPU（那篇 Flow Matching 有 161 條公式），截圖工具可能等不到而報
「renderer frozen」。**那通常不是壞掉，是還在排版**。改用取頁面文字的方式看內容
（Chrome 工具的 `get_page_text`），它輕得多，而且**逐詞讀得到轉換品質**——
第一次跑這個 skill 就是這樣讀出兩個詞彙轉錯的。

## 看的時候看什麼

測試抓不到的，就是這個 skill 要抓的。已知會漏的四類：

- **只轉了一半**：後端對 A 欄位做了處理、B 欄位忘了（標題 vs 正文就是這樣漏的）。
  **對照畫面上每一處顯示同類內容的地方**，不只你改的那一處。
- **詞撞名**：新按鈕／新標籤的用字，在這一頁上是不是已經指別的東西。
  取名前 `grep` 那個詞在 `frontend/src/` 的既有用法（experience 有一條專講這個）。
- **渲染層才會炸的東西**：LaTeX、markdown、圖片、CJK 排版——單元測試看的是字串，
  使用者看的是渲染結果。
- **空狀態與長內容**：測試資料通常剛好，真實資料通常不是。
- **機器轉換／生成的輸出要逐詞讀，不是掃過**：整段看起來通順，錯的是其中一兩個詞。
  掃過去只會覺得「好像對」。

## 之後

看到問題 → 先補一條會失敗的測試再修（憲章 I），別直接修。
蒸餾得出判準 → `/knowie-capture`。改了某個決定 → 那是轉移，進 `history/`。
