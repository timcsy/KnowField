# history/078：re-platform 里程碑二收尾＋三＋五——舊 Jinja/DaisyUI 全退場

**日期**：2026-08-06 · **階段**：vision 階段 27 里程碑二/三/五（收官）· 承 `history/077`

## 做了什麼

- **里程碑二收尾（補完次要功能，退場前必補）**：conversation 單篇檢視加 **章節（`/api/conversations/{id}/segment`）＋重生標題（`/retitle`）**；`Markdown` 元件加**圖片 hotlink 失效→替代連結** fallback；ChatPage 加 **💾 存下這段（`/api/chat/save`）**；IngestPage 加 **YouTube 逐字稿（`/api/ingest/youtube`）**。（chat 匯出/編輯、ingest rich-paste、roots 複製鈕在 077 已到位。）
- **里程碑三（web 測轉 API）**：新增 `test_api_pages`（library/source/ingest/conversations/dedupe 的 `/api` 覆蓋）當安全網；`test_temp_save_web`/`test_export_web` **repoint 到 `/api`**（行為同一份服務閉包，只換門面）。
- **里程碑五（退場）**：刪 `templates/`（10 檔，DaisyUI 唯 `base.html` 載）＋其**全部 Jinja HTML 路由（472 行）**＋`Jinja2Templates`/`_TEMPLATES`/`HTMLResponse`；`/`、`/ask`→`/app/`；`OpenAIError` handler→`PlainText`。**保留**全 helper/factory、`/api/*`、SPA 服務、三 export 端點（chat/conv/roots）。刪 9 個純 Jinja web 測檔、4 檔動刀刪 web 綁定類別。

## 為何這樣（而非早點 big-bang 退場）

077 刻意擋住退場：**退場＝刪舊版，若次要功能未遷＝刪掉還在用的功能**。所以先補完（redeem）再退（retire）。退場當下又發現兩個「只在 Jinja、React/`api` 沒有」的真功能——**YouTube 逐字稿收進**、**獨立存對話成永久**——沒有默默丟掉，而是補 `/api/chat/save`＋`/api/ingest/youtube`＋前端鈕，才刪。原則：退場不得偷換功能（反逢迎於自身）。

## 接受的次要省略（誠實記，非默默丟）

chat **分支(branch)**（SPA 無持久化前綴、成本高，能以「編輯訊息重問」替代）、收尾 **distill-nudge**（提醒性 UX）、**逐章 distill**（章節已可看＋整段可 distill）。皆邊緣 UST、結果可由現有路徑達成；要時再補。

## 守住的紅線
膜/純度（stream/distill 不寫地基）／人閘門（唯 `/api/chat/anoint` 寫 bedrock）／溯源（結構化來源）／暫存不注入回場（原則 5/6）——皆在後端服務閉包不動，測仍綠。**288 測綠、零回歸**；`tsc+vite build` 綠；核心 Python 零相依不變。

## 結果
**React 成唯一門面**，舊 Jinja/DaisyUI 徹底退役。vision 階段 27 全 5 里程碑完成 → 前端 re-platform 收官。下一步接上線基座：auth/多租戶（`draft/共享的膜與跨base聯邦` A/B）。
