# Tasks：從對話生文章（spec 043 · 階段 39）

**TDD**：先紅再實作。⚠️ FR-002／FR-003 是沉默失效型，兩條都要**反向攻擊**。

## Phase 1：生成核心（純函式層）

- [X] T001 `tests/unit/test_article_pinned.py` —— **先紅**
      ① pinned 全部被納入（正文＋延伸合計）
      ② ⚠️ **embedder 為 None**（排序停用）時 ① 仍成立（SC-002）
      ③ ⚠️ pinned 中的 `猜想` **不在正文**（SC-003）
      ④ pinned 只有 2 條時正文 > 2 條（SC-004）
      ⑤ 未給 pinned 時輸出與現況**逐字相同**（SC-005）
- [X] T002 `src/knowfield/output/article.py`：`generate_article(..., pinned=None)`
      —— 只改「排序」那一步，**分流那兩行一個字都不動**
- [X] T003 ⚠️ 反向攻擊：把 pinned 直接塞進 `body`（繞過分流），確認 ③ 轉紅
- [X] T004 ⚠️ 反向攻擊：改成「pinned 也丟進 `_rank_by_topic` 排序、不釘住」，確認 ② 轉紅

## Phase 2：路由

- [X] T005 `tests/contract/test_article_from_conversation.py` —— **先紅**
      ① 帶 `conversation_id` → 文章含該對話的 referrers
      ② referrers 為空 → 回可行動訊息（非空白、非 5xx）
      ③ 不帶 `conversation_id` → 請求/回應與現況逐字相同
      ④ 對話不存在 → 明講找不到
      ⑤ 已儲存內容不變（FR-008）
- [X] T006 `src/knowfield/web/app.py`：`/api/article` 接 `conversation_id`；記一行 log
- [X] T007 ⚠️ 反向攻擊 ③：偷改未帶對話時的行為，確認轉紅

## Phase 3：前端

- [X] T008 `frontend/src/lib/api.ts`：`generateArticle` 帶 `conversation_id`
- [X] T009 `frontend/src/ChatPage.tsx`：「⋯ 更多」加一顆入口；
      ⚠️ referrers 為空時**不要灰掉了事**，要說「先精選」（FR-006）
- [X] T010 `npm run build` ＋ `npm run test -- --run` 綠

## Phase 4：驗收

- [X] T011 `uv run pytest -q` 全綠（SC-006）
- [X] T012 ⚠️ 瀏覽器真跑：用對話 #17（15 條 referrers）與 #23（2 條，含 1 條 `類比`）各生一篇，
      比對 References 是否涵蓋、`類比` 是否落在延伸閱讀
- [X] T013 反流 → 出貨（用 `ship-knowfield` skill）


---

## 實作／真跑的三次自我修正（2026-08-22）

- [X] T014 ⚠️ **SC-001 原本驗不到**：寫成「在 References 中出現」，但 `_references()`
      （`article.py:65`）渲染的是 URL 或「（你收藏的來源）」、**根本不含主張**。
      正文節點的主張只存在於**送給模型的 prompt**。→ 改測 prompt，並回頭改了規格。
- [X] T015 ⚠️ **T007 的第一版攻擊是 no-op**：釘住 `nodes[:2]` 剛好就是原本排最前的兩條，
      輸出完全沒變 ⇒ 撞不紅不代表測試沒牙齒。改成釘 `nodes[-2:]` 才真的撞紅。
      （`experience.md`：反向攻擊撞不紅 ≠ 實作正確；但這次是**攻擊本身**沒實作那個 bug。）
- [X] T016 真跑（對話 #23，2 條 referrers）：`pinned=2, field=34`；
      `已證實` 那條進正文並被引用 `[4]`，`類比` 那條落在**延伸閱讀**標 🌉——分層沒被繞過。
