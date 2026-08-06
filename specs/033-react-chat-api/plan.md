# 技術方案：前端 re-platform 階段一（/chat React ＋ /api）

**目錄**：`033-react-chat-api` · **狀態**：Plan · **前置**：spec.md、vision 階段 27、history/075

## Technical Context
- 前端：React 19＋Vite 8＋TS＋Tailwind v4＋shadcn/ui（`frontend/`，phase 0 已成）。
- 後端：FastAPI 加 `/api/*` JSON/SSE 端點，**共用既有 create_app 內的服務閉包**（不重寫邏輯）；並服務 `frontend/dist`。
- 靈魂在 `field_chat`（`_MEMBRANE`/`build_field_system_prompt`/`reply_stream`/`distill`）——不動。

## Constitution Check
- **IV 簡潔/YAGNI**：複雜度只在前端層，理由已記 history/075；後端只加薄門面。✅
- **II 全繁中**、**V 明確錯誤**（教訓 3 邊界攔截）、**VI 決策主權**（精選人閘門）。✅
- 原則 3/5/6 守衛延續（溯源結構化、人閘門、純度守衛）。✅

## Phase 0：關鍵決策
1. **/api 怎麼共用既有邏輯？** → 抽兩個 create_app 內閉包 helper：`_stream_gen(hist,msg,bs)`（/chat/stream 與 /api/chat/stream 共用）、`_do_anoint(...)`（/chat/anoint 與 /api/chat/anoint 共用）。其餘 /api 直接呼叫既有 `chat_factory`/`distill_factory`/repo。**零邏輯重寫、行為天然一致**。
2. **/api 收 JSON**：`await request.json()`（React 送 JSON）；回 `JSONResponse`；串流回 `StreamingResponse` text/event-stream（協定不變：stage/token/done/error）。
3. **服務 SPA（strangler，不搶舊路由）**：React build 掛在 **`/app`**（Vite `base:'/app/'`）；`/app/{path}` fallback 回 `index.html`；舊 `/`、`/chat` 等 Jinja **不動**。dist 不存在時 fallback 提示（dev 走 Vite dev server proxy）。
4. **前端測試**：本階段只後端 API 測（pytest）＋人工視覺；前端測框架留後續。

## Phase 1：Design
### /api 端點（共用既有服務）
- `GET /api/chat/state` → `{root_count, recent_temp}`（＝GET /chat 資料）
- `POST /api/chat/stream`（JSON {history,message,brainstorm}）→ SSE（`_stream_gen`）
- `POST /api/chat/distill` → `{candidates:[...]}`（distill_factory）
- `POST /api/chat/anoint` → `{status,claim,msg}`（`_do_anoint`；人閘門）
- `POST /api/chat/autosave` → `{temp_id}`（既有邏輯）
- `GET /api/roots` → `{anointed, candidates, provenance, source_provenance}`
### SPA 服務
- `frontend/vite.config` prod `base:'/app/'`；FastAPI `StaticFiles` 掛 `/app/assets`＋`GET /app/{path:path}` 回 index.html。
### React /chat（`frontend/src`）
- `lib/api.ts`（fetch 包 /api）＋ `ChatPage`（側欄殼＋訊息串＋SSE 串流 hook＋整理→候選→人精選＋引用[n]錨點＋你收藏的＋腦力激盪＋autosave）。shadcn：button/card/textarea/badge/scroll-area。

## 測試策略（TDD）
- `tests/unit/test_api_chat.py`：state shape、stream 吐 SSE（注入 stub backend）、distill 回候選、**anoint 只人閘門＋純度守衛（未精選不進地基）**、roots shape、autosave。
- SPA 服務：`GET /app/`（或 /app/chat）回 HTML（dist 存在時）——輕測或條件跳過。
- 既有 345 測不回歸；核心邏輯不動。
