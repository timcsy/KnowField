# 014：前端美化——選 DaisyUI，否決 React SPA
> 日期：2026-07-24

## 轉移
- 舊：web 頁面用基本 Tailwind，功能到位但陽春。
- 新：改用 **DaisyUI**（Tailwind 元件庫，CDN、**零 build**）美化——卡片、navbar、badge、
  hero、join 輸入、`nord` 主題。**server-render 架構完全不動、無 React/Node、127 測試不受影響**。

## 為什麼變 / 為什麼是 DaisyUI
使用者希望「前端好看一些」，並問可否用 React。釐清後認清：**「好看」是設計/CSS 的事，
不是 React**（React 帶的是客戶端互動，不會自動變好看）。使用者真實痛點是「太醜」，
故選最省力的 A：DaisyUI 元件庫，兩行 CDN、零 build，馬上大幅提升觀感。

## ⚰️ 否決：React SPA（Vite＋React＋FastAPI 轉 JSON API）
- **考慮過**：最現代、互動最強。
- **為何不選**：會引入 **Node／npm／build pipeline**、前後端拆分——是比 Tailwind/DaisyUI
  大得多的偏離「零相依」，維護面也更重。對「只是想變好看」的需求是殺雞用牛刀（YAGNI）。
- 若日後真需要複雜客戶端互動，再重啟評估（屆時進路線圖）。
- （中間路線 HTMX＋Tailwind 亦考慮過，同樣未選——A 已滿足需求。）

## 影響
- 只改 `web/templates/`（base/_entry/digest/pull/interests/error）；程式邏輯零改動。
- 相依只多兩行 CDN（DaisyUI＋Tailwind Play CDN），無新增 Python/Node 套件。
- commit `71b3579`。

## 狀態
✅ 已採用（React SPA 留墓碑，需要時再議）
