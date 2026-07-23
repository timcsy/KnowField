# Phase 0 研究：Web 介面

技術棧已於 knowie 定案（FastAPI＋Jinja2＋Tailwind，見 `knowledge/draft/2026-07-23-部署
與介面路線.md`）。此處只記本階段實作決策。

## R1. Server-render 樣式（FastAPI＋Jinja2）
**決策**：FastAPI 路由回 `HTMLResponse`，用 Jinja2 模板 server-render；不引入前端 SPA。
頁面：`base.html`（版型＋Tailwind）、`digest.html`、`pull.html`、`interests.html`。
**理由**：個人工具、內容以「讀」為主，server-render 最簡、SEO/首屏都好；符合原則 IV。
**替代**：SPA（React/Vue）——過重、違 YAGNI，spec 已列範圍外。

## R2. Tailwind 導入方式
**決策**：MVP 用 **Tailwind Play CDN**（`<script src>` 一行，零 build），語意 HTML＋
utility class 直接 RWD。日後正式再上 Tailwind CLI build（產最小 CSS）。
**理由**：零 build＝最快起步、貼「先簡單」；個人工具用 CDN 足夠。
**替代**：一開始就上 build pipeline——增複雜度，MVP 不需。

## R3. 即時拉的快取／節流（FR-005／SC-004）
**決策**：`web/cache.py` 一個**記憶體 TTL 快取**，key＝正規化主題，值＝PullResult；
TTL（如 10 分鐘）內同主題直接回快取、不打後端。另加簡單節流（同主題最小間隔）。
**理由**：即時拉＝即時 LLM 呼叫，重複主題狂打後端會爆成本（見 draft 開放問題）。記憶體
快取對本機單人最簡有效。
**替代**：Redis／持久快取——本機單人過度，YAGNI。

## R4. 後端失敗的錯誤邊界（FR-009／原則 V、教訓 3）
**決策**：FastAPI 註冊 `OpenAIError`（及其他預期錯誤）的 **exception handler**，回一個
友善的繁中 HTML 頁面（說明「後端暫不可用，可稍後重試或用離線模式」），**不噴 500 堆疊**。
**理由**：延續 experience 教訓 3（外部相依必失敗、在邊界攔）；web 的邊界＝例外處理器。

## R5. 首頁讀哪份匯整
**決策**：首頁讀**最近一次落庫的匯整**（`digest_entries`）。新增
`repository.get_last_digest()` 回該匯整的全部 entries（標題／原文連結／散文／圖）。
尚無匯整時顯示空狀態，提示去跑 `learnnews digest`。**web MVP 不主動觸發每日匯整產生**
（屬排程/CronJob 的事，見階段 7–9）。
**理由**：讀既有最簡、責任分明；產生匯整是 CronJob 的職責，不混進 web 請求。

## R6. 散文與圖的 HTML 呈現
**決策**：散文本體以段落（依空行切）轉成 `<p>`，**HTML 逸出**避免注入；原文圖以
`<img loading="lazy">` 內嵌，AI 圖在圖說標「AI 示意・非原文」；每則標題下放原標題副標
與一鍵原文 `<a>`。
**理由**：忠實呈現既有 Article／Figure；lazy load 對多圖友善；逸出保安全。

## 未決 → 全部解決
Technical Context 無殘留 NEEDS CLARIFICATION。
