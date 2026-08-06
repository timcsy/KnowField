# history/075：前端 re-platform → React + Vite + shadcn/ui（含憲章 IV 複雜度理由）

**日期**：2026-08-06 · **類型**：架構轉向（前端）· 供料：一整段 UI 迭代後的使用者定案

## 轉變（why）——且這是對前一決策的推翻，記轉折

`draft/2026-07-23-部署與介面路線` 原本的定案是「**UI＝設計 pass＋htmx，不是 React 全重寫**」（rejected React，理由＝重寫陷阱＋憲章 IV）。**本次使用者推翻它、選 React**——決策主權（憲章 VI），且在攤開全部成本後做的自覺選擇。推翻的理由：

1. **想要「大多數 AI 產品的樣子」**：實查後確認那個樣子＝**shadcn/ui**（Tailwind＋Radix，React 原生）。DaisyUI（CDN、不能配置）一路要用 `!important` 對幹它的預設，是**跟框架對幹的內耗**——換 shadcn 就不用再對幹。
2. **要上線給別人用**（auth／多租戶／`knowfield.tew.tw`）——JSON API＋SPA 是自然基礎。
3. **手機分享網頁進 App**：＝ **PWA Web Share Target API**（Android 可靠；使用者是 Android）。Vite＋`vite-plugin-pwa` 是做 PWA/share_target 最順的路——選 React/Vite 讓這個目標近乎免費附帶。後端只要多一個 `/api/ingest/share` 接分享。
   - iOS 註記：Web Share Target 在 iOS 不可靠（本專案不需，使用者 Android）。

## 憲章 IV（簡潔與 YAGNI）的複雜度理由——依 IV 自身要求記錄

憲章 IV 原文：「僅在有明確且當前的需求時才引入…相依/複雜度…任何額外複雜度 MUST 在計畫的複雜度追蹤中提出理由」。
→ **不算違憲，是依 IV 要求提理由**：引入 Node build 鏈＋React 的當前明確需求＝(a) 產品外觀對齊業界標準、(b) 上線多租戶、(c) PWA 分享。
**核心零相依不變**：Python 核心（chunk/ingest/distill/rag/repository）不動，仍 stdlib＋OpenAI urllib；複雜度只在**前端這層**（本就是框架相依被隔離之處）。

## 技術棧（定案）
- **前端**：React 19 ＋ Vite 8 ＋ TypeScript ＋ Tailwind v4 ＋ shadcn/ui（new-york、neutral base，之後調暖）。落在 `frontend/`。
- **後端**：FastAPI 保留、轉成 **JSON API**（`/api/*`）；正式環境由 FastAPI 吐 Vite build 靜態檔（單一服務、好部署）。開發＝Vite dev server proxy `/api`→:8000。
- **PWA**：`vite-plugin-pwa` 設 manifest＋`share_target`（後續階段）。

## 本次落地（骨架驗證）
`frontend/` scaffold：Vite React-TS ＋ Tailwind v4（`@tailwindcss/vite`）＋ shadcn（button/card）＋ `@` 別名 ＋ `/api` proxy。`tsc -b && vite build` 綠（已移除 TS7 deprecated 的 baseUrl，paths 相對 tsconfig 解析）。

## 階段（strangler、不 big-bang）
1. ✅ 骨架＋工具鏈驗證（本次）。
2. `/chat` 打樣（核心＋串流）＋後端 `/api` 首批端點。
3. 逐頁遷：roots → library → source → ingest → conversations（舊 Jinja 頁在被取代前照跑）。
4. web 測（驗 HTML）→ 改 API 測；核心邏輯測不動。
5. PWA＋`/api/ingest/share`（Android 分享）。
6. 全遷完 → 舊 Jinja 模板＋DaisyUI 退場。

## 未竟／關聯
- 這推翻 `draft/部署與介面路線` 的「htmx>React」段（該段已標 superseded→本 history）。
- 上線 auth／多租戶見 `draft/共享的膜與跨base聯邦` 的 A/B/C 分階（JSON API 是共同基礎）。
- **已立 vision 階段 27**（2026-08-06 promote，phase 0 骨架完成、階段一起跑）；逐階 promote 成 spec。
