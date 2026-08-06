# history/074：專案改名 LearnNews → KnowField

**日期**：2026-08-06 · **類型**：產品識別轉變（非功能）

## 為什麼改（why）

`LearnNews` 是**新聞分診 MVP** 時期的名字。產品早已轉向——階段 16「反逢迎的當下副手」把北極星從「每日新聞分診」翻成
「站在你個人知識場上、幫你挖到 bedrock、且絕不逢迎的當下副手」，階段 17–26 一路蓋在這上面。「News」名不符實已久。

**為何是 KnowField**：直白（know＋field＝**知識場**），而且 literally 命名了產品的**母概念**〈有吸引子的**場**〉——
名字直接說出系統在做什麼。使用者要的正是「直白、和學習知識＋腦力激盪有關」的名字。

## 候選與否決（挑名的 why behind why）

- **Brainstore**（使用者初選）→ 否決：類別三重佔用（Braintrust 的 AI DB 產品＋瑞士點子公司 brainstore.com＋App Store app＋ai-brainstore 開源），乾淨 .com 拿不到、SEO/商標都擠。
- **Brainkeep** → 較乾淨（AI 知識類別無人用），但 `.com` 被拉斯維加斯軟體代理商佔、商標中等風險。
- **KnowField** → **選定**：AI 知識/學習類別完全清場（唯一同名 KNOWFIELD LIMITED 是 2016 解散的英國 non-trading 空殼）；
  直白且命中母概念。
- 其他丟過的方向：Fathom/Keel/砥（隱喻，被「要直白」否決）；學思/思辨/會悟（中文直白備選）。

## 網域

`knowfield.com` 被佔且使用者也不要 .com；**用自有網域子域 `knowfield.tew.tw`**（免註冊、零衝突，之後上線加登入方便）。

## 怎麼改（what，一次到位）

使用者定案「整個專案一次全部都改」（非分段）。本 session 完成的機械 rename：
- `git mv src/learnnews → src/knowfield`（保 git 歷史）；`learnnews.db → knowfield.db`（改前已備份 `learnnews.db.bak-rename-*`）。
- 全域三種大小寫 sed：`learnnews→knowfield`（import/package/db 路徑）、`LEARNNEWS→KNOWFIELD`（env 變數前綴）、
  `LearnNews→KnowField`（對外顯示名）。涵蓋 src/、tests/、knowledge/、specs/、pyproject、`.claude/skills/`。
- `.env` 盲改前綴 `LEARNNEWS_→KNOWFIELD_`（未讀內容，守「不讀/印 .env」規矩）。
- 重裝（`uv sync --all-extras`）重生 egg-info；`pyproject` name/script 已為 knowfield。
- 驗收：**345 測綠、零回歸**；server 以 `KNOWFIELD_DB=knowfield.db uv run uvicorn knowfield.web.app:create_app` 起、
  新 db 讀得到既有 34 根因/8 來源、標題已 KnowField。

## 未竟

- **UI 重寫/美化**：使用者另提（覺得現 Jinja2 醜/難用），評估結論傾向「設計 pass＋htmx、非 React 全重寫」（撞憲章 IV），**未定案、押後**。
- 舊備份 `learnnews.db.bak-rename-*` 暫留（安全），確認無誤後可刪。
