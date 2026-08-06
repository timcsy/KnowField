# history/076：re-platform 階段一——/chat React ＋ /api 基座（spec 033 完成）

**日期**：2026-08-06 · **階段**：vision 階段 27 里程碑一 · **spec**：`specs/033-react-chat-api/`

## 做了什麼（why：證明整條新管線可行、且不掉靈魂）

用核心頁 `/chat` 打通 **React SPA → FastAPI JSON/SSE `/api` → 既有服務**，證明 re-platform 走得動，且**後端邏輯（膜/反逢迎/串流/整理/精選）一律不動**——React 只換臉。

## 關鍵設計（零邏輯重寫、行為天然一致）

- **抽兩個 create_app 內共用閉包**：`_stream_gen(hist,msg,bs)`（`/chat/stream` 與 `/api/chat/stream` 共用）、
  `_do_anoint(...)`（`/chat/anoint` 與 `/api/chat/anoint` 共用）。其餘 /api 直呼既有 `distill_factory`/repo。
  → HTML 舊路由與 /api 共用同一份邏輯，**新舊行為天然一致**、無兩套飄移。
- **/api（`await request.json()` 收 JSON、回 JSONResponse/SSE）**：`GET /api/chat/state`、`POST /api/chat/stream`（SSE
  協定不變 stage/token/done/error）、`/api/chat/distill`、`/api/chat/anoint`、`/api/chat/autosave`、`GET /api/roots`。
- **服務 SPA 於 `/app`**（strangler）：Vite `base:'/app/'`；FastAPI `StaticFiles` 掛 `/app/assets`＋`/app/{path}` fallback
  回 index.html；**舊 Jinja `/`、`/chat` 完全不動**。dist 不存在時不註冊（dev 走 Vite proxy）。
- **前端**：`frontend/src/lib/api.ts`（fetch＋SSE reader）＋`ChatPage.tsx`＋`App.tsx`（側欄殼）。shadcn：button/card/textarea/badge。

## 守住的紅線

- **原則 5/6 人閘門＋純度**：守衛測 `test_anoint_human_gate_only_writes_bedrock`——distill 只候選、不寫地基；唯 `/api/chat/anoint`（人按）寫。冪等去重（exists）也測。
- **原則 3 溯源靠結構**：`/api` 回**結構化 sources**（n/url/title/kind），React 把 `[n]` 接錨點、`kind==corpus` 標「你收藏的」——不靠模型自律。守衛測 `test_stream_sse_with_structured_sources`。
- **膜不動**：`field_chat`（`_MEMBRANE`/`build_field_system_prompt`/`reply_stream`/`distill`）零改動。
- **strangler**：`test_old_jinja_chat_still_works`——舊 `/chat` 照跑。
- **憲章 IV**：核心 Python 零相依不變；複雜度只在前端。

## 驗收

**345→355 測綠、零回歸**。10 條新測：8 `/api`（state/stream/brainstorm/distill/anoint人閘門+純度/冪等/roots/autosave）＋strangler＋SPA 服務。`tsc+vite build` 綠。server 起後 `/app/` 200、舊 `/chat` 200、`/api/chat/state` 回真資料（34 核心理解）；React /chat 真跑、真吃 /api。

## 未竟（本階段 polish ＋ 後續里程碑）

- **本階段 polish**：答案 markdown/MathJax 渲染仍陽春（whitespace-pre-wrap＋[n] 錨點）；編輯/分支、數學複製尚未移植——留補齊。
- 里程碑二～五（逐頁遷 → 測試轉 API → PWA share_target → 舊 Jinja/DaisyUI 退場）見 vision 階段 27。
