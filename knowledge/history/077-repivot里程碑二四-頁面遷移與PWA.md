# history/077：re-platform 里程碑二（核心）＋四（PWA）——頁面遷移與手機分享

**日期**：2026-08-06 · **階段**：vision 階段 27 里程碑二/四 · 承 `history/076`（階段一）

## 做了什麼

- **里程碑二（核心）**：roots/library/source/ingest/conversations **主頁面遷 React**（react-router `basename=/app`、shadcn、共用 `Markdown` 元件＝渲染＋MathJax＋**選取複製 LaTeX**、全站掛一次）。後端加對應 `/api`（whynode/library/source(+meta/distill/reclassify/remove)/ingest(paste/url/pdf)/conversations(+detail/rename/promote)/dedupe），全**共用既有 repo/service**。
- **門面轉 React**：`GET /` → `/app/`（dist 已 build 時）；`ChatPage` 支援 `?resume=id` 接回存下的對話。
- **里程碑四（PWA）**：`vite-plugin-pwa` manifest（standalone/暖色/icon.svg）＋`share_target`(`/app/share-target`)；後端 `SpaStatic` 正確服務 manifest/sw/icon（非 fallback 成 HTML）＋client-route fallback；`POST /app/share-target` 收分享網址/文字→收進→導回 library。**Android 上線（HTTPS＋裝 PWA）即可「分享網頁進 App」。**

## 守住的紅線
膜/純度/人閘門/溯源皆在後端不動、React 忠實呼叫（history/076 已立守衛測）。strangler：舊 Jinja 全站照跑。358 測綠、零回歸；`tsc+vite build` 綠；核心 Python 零相依不變。

## ⚠ 退場（里程碑五）被擋——誠實記，避免刪掉還在用的功能

React 版目前是**各頁核心已遷，但次要功能未遷**：chat 匯出(複製 MD/來源)＋編輯/分支、ingest **rich-paste(貼圖文)**＋剪貼簿鈕、roots 複製鈕、conversation **單篇檢視＋章節**、source 圖片 fallback。
**因此不能刪 Jinja/DaisyUI**——退場＝刪舊版＝會刪掉這些尚未遷的功能。舊 Jinja 現為**完整 fallback、照跑**；退場前**必須先補完這些功能**（＝里程碑二收尾），再做里程碑三（web 測轉 API）＋五（退場）。這是刻意不趕、避免以「假完成」換掉真功能（反逢迎於自身）。

## 未竟（依序）
1. 里程碑二收尾：補 chat 匯出/編輯分支、ingest rich-paste、roots 複製、conversation 檢視/章節、source 圖 fallback。
2. 里程碑三：web 測（驗 HTML）→ API 測。
3. 里程碑五：刪 Jinja 模板＋DaisyUI（redeem-and-retire）。
