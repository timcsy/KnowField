# Implementation Plan: 對話暫時存檔（自動、TTL 衰減）＋永久存檔（人閘門）

**Branch**: `028-temporary-save` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/028-temporary-save/spec.md`

## Summary

`conversations` 加 `temporary`（0=永久/1=暫存）＋`last_activity_at` 兩欄。**自動暫存**＝`autosave_temporary(temp_id, messages, now)`（**id-upsert 一筆**，非每輪新增；與 spec 025 的 fingerprint-dedup 分開，因暫存內容逐輪變）；client 每輪串流完成後 best-effort POST `/chat/autosave`、記回 `temp_id`。**TTL 衰減**＝純函式 `expired_temp_ids(convos, now, ttl_days=7)`＋**懶清** `purge_expired_temporary`（載 `/conversations`／存檔時清、不開背景）。**升永久**＝`promote_conversation(cid, 落點標題)`（同一筆 temporary→0，人按）。既有 spec 023 存檔一律 permanent。

## Technical Context

**Language/Version**: Python 3.12+（uv）
**Primary Dependencies**: 既有 FastAPI＋Jinja2；TTL 判準核心**零第三方相依**（stdlib datetime）
**Storage**: SQLite——conversations **加 2 欄**（temporary、last_activity_at；冪等 migrate＋回填既有=永久）；不新增表
**Testing**: pytest（現 441 綠）
**Target Platform**: 本機 web（單使用者）
**Project Type**: web（FastAPI＋Jinja2）
**Performance Goals**: autosave＝每輪一次 upsert（無 LLM、便宜）；TTL 判準 O(對話數)
**Constraints**: 不囤積（暫存衰減）、不污染（暫存不注入回場）、人閘門升永久、懶清不開背景、離線可測、全繁中、核心零相依
**Scale/Scope**: 個人場；2 欄＋純函式 1＋repo 4 法＋4 路由＋chat autosave/接回 UI＋/conversations 分區

## Constitution Check

*GATE：Phase 0 前必過；Phase 1 後複查。*

- **I. TDD** ✅ `expired_temp_ids` 純函式先紅後綠；autosave upsert（一筆）／promote／purge repo 測；**不注入回場守衛測**（比照 spec 023 SECRET_FANTASY）。
- **II. 繁中** ✅ 全繁中。
- **III. 規格驅動** ✅ 可追溯 FR-001…012。
- **IV. YAGNI** ✅ 複用 conversations／title（spec 027）；**2 欄**、無新表；懶清不做背景排程；暫存便宜標題不呼 LLM。
- **V. 可觀測性／錯誤** ✅ autosave best-effort 不擋聊天、空對話不存（教訓 3）。
- **VI. 決策主權／原則 5·6** ✅ **升永久人按**；**暫存衰減＝不囤積機制化**（原則 6）；暫存不注入回場（守衛測）。

**結論：無違憲。加 2 欄正當（暫存/永久是新的生命週期屬性）——冪等 migrate、既有存檔回填為永久，不破。**

## 關鍵設計決策（詳見 research.md）

1. **暫存 upsert（id）與永久存（fingerprint dedup）分開**：暫存內容**逐輪變**，不能用 spec 025 的內容指紋 upsert；改
   **client 持 `temp_id`、id-upsert 同一筆**。永久手動存維持 spec 025 fingerprint dedup（temporary=0）。
2. **升永久＝promote 同一筆**：client 把 `temp_id` 帶進「存這段/冊封連同存/轉永久」→ `promote_conversation(temp_id, 落點標題)`
   翻 temporary=0、不新增重複；無 temp_id（罕見）→ 退回 `save_conversation`（建永久）。
3. **TTL 純函式＋懶清**：`expired_temp_ids(convos, now, 7)`（stdlib parse ISO、比較）。`/conversations` 載入與存檔動作
   先 `purge_expired_temporary(now)`。**不開背景排程**（原則：能懶清就別背景）。
4. **暫存便宜標題**：首句截斷（非 LLM，省成本、免每輪呼）；升永久時才生 spec 027 落點標題。
5. **接回**：`/chat` 載入時，若有最近暫存 → 顯示「上次還沒存的對話還在，接回嗎？」→ resume 載入該暫存（帶回 `temp_id`、
   touch 重設 last_activity），續聊 autosave 更新同一筆。

## Project Structure

### Documentation (this feature)
```text
specs/028-temporary-save/
├── plan.md · research.md · data-model.md · quickstart.md
├── contracts/temporary-save.md
└── tasks.md（/speckit-tasks 產出）
```

### Source Code (repository root)
```text
src/learnnews/
├── chat/
│   └── capture.py              # 【改】加 expired_temp_ids(convos, now, ttl_days=7)＋cheap_title(messages)（純、零相依）
├── models/__init__.py          # 【改】Conversation 加 temporary、last_activity_at
├── store/
│   ├── schema.py               # 【改】conversations 加 temporary＋last_activity_at；_migrate 冪等＋回填(既有=永久、last_activity=created_at)
│   └── repository.py           # 【改】autosave_temporary(id-upsert)／promote_conversation／purge_expired_temporary／touch；list/get 帶新欄
└── web/
    ├── app.py                  # 【改】POST /chat/autosave；/chat/save＋/chat/anoint 收 temp_id→promote；
    │                           #   POST /conversations/{cid}/promote；/conversations 懶清＋分區＋帶最近暫存給 /chat 接回橫幅
    └── templates/
        ├── chat.html           # 【改】串流 done 後 best-effort autosave＋記 temp_id(hidden＋localStorage)；接回橫幅
        └── conversations.html  # 【改】分「永久／暫存（會自動清除）」兩區；暫存每筆「轉永久」

tests/unit/
├── test_capture_core.py        # 【擴】expired_temp_ids（過期/未過期/邊界/永久不選/計時重設）＋cheap_title
└── test_temp_save_web.py       # 【新】autosave 一筆 upsert／best-effort 不崩／空不存；懶清只刪過期暫存不動永久；
                                #   promote 同一筆不重複＋落點標題；既有存檔=永久；不注入回場守衛
```

**Structure Decision**: 沿用單一 web 專案。TTL/便宜標題純核心進 `chat/capture.py`；repo 加暫存生命週期 4 法；web 加 autosave/promote 路由＋接回；`/conversations` 分區。無新表、無新相依。

## Complexity Tracking

| 變更 | 為何需要 | 較簡替代被否原因 |
|---|---|---|
| conversations 加 `temporary`＋`last_activity_at` | 表達「暫存/永久」生命週期與 TTL 衰減——現無此屬性 | 純 localStorage：不跨裝置、衰減無法伺服器端一致清；新表：一段對話一列即可，過度 |
| autosave 用 id-upsert（非 spec 025 fingerprint dedup） | 暫存內容逐輪變、指紋每輪不同無法 upsert 同筆 | fingerprint dedup：會每輪新增一筆＝囤積，違本 spec 本意 |
