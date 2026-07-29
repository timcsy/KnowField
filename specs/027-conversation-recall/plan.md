# Implementation Plan: 對話的可找回性——落點重命名＋章節切分

**Branch**: `027-conversation-recall` | **Date**: 2026-07-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/027-conversation-recall/spec.md`

## Summary

解「長對話找不回」：**US1 重命名**——`FieldChat.title` 取材由「只看開頭 `convo[:2000]`」改為**首尾並取**（純函式 `title_material`）＋提示強調落點/全貌；加 `rename_conversation`＋改名/重生路由。**US2 章節切分**——可注入 `FieldChat.segment`（LLM 判轉折，stub 離線可測）＋純函式 `normalize_chapters`（涵蓋全對話、不重疊、失敗退回整段一章）；on-demand 算、**不落庫**。**US3 每章動作**——匯出加 `from/to` range 切片（複用 spec 024）＋「整理這章」就切片走既有 distill→冊封。無新表。

## Technical Context

**Language/Version**: Python 3.12+（uv）
**Primary Dependencies**: 既有 FastAPI＋Jinja2；LLM 走既有可插拔 chat backend（注入 stub 測）；純核心零第三方相依
**Storage**: SQLite——US1 只 `UPDATE conversations.title`；**章節不落庫**（US2 on-demand）；不新增表/欄
**Testing**: pytest（現 423 綠）
**Target Platform**: 本機 web（單使用者）
**Project Type**: web（FastAPI＋Jinja2）
**Performance Goals**: 標題取材/章節正規化 O(對話長度)；LLM 呼叫人手動觸發、非每輪
**Constraints**: 人閘門（不自動改名/切分/冊封）、離線可注入測、章節不落庫（原則 6 過度擬合守）、全繁中、核心零相依
**Scale/Scope**: 個人場；2 純函式＋FieldChat 改 title/加 segment＋repo 1 法＋5 路由＋conversation 頁大綱 UI

## Constitution Check

*GATE：Phase 0 前必過；Phase 1 後複查。*

- **I. TDD** ✅ `title_material`／`normalize_chapters` 純函式先紅後綠；title/segment 注入 stub 測；rename/每章切片 web 測；守衛（不自動改名/切分/冊封）。
- **II. 繁中** ✅ 全繁中。
- **III. 規格驅動** ✅ 可追溯 FR-001…012。
- **IV. YAGNI** ✅ 複用 distill／spec 024 匯出；**無新表**；章節 on-demand 不落庫；切材/正規化抽純函式。
- **V. 可觀測性／錯誤** ✅ title 失敗退首句、segment 失敗/過短退整段一章（教訓 3）。
- **VI. 決策主權／原則 6** ✅ 改名/重生/切分/每章冊封**人按才做**；章節不落庫＝先驗 payoff 再談重做（過度擬合守）。

**結論：無違憲。章節切分較投機——以「on-demand 不落庫＋輕量大綱＋人觸發」把過度擬合風險關在門外（可隨時廢，不留結構債）。**

## 關鍵設計決策（詳見 research.md）

1. **標題成因＝取材截頭**：現況 `title` 餵 `convo[:2000]`＝只看開頭。改純函式 `title_material(messages)`＝**首段＋尾段並取**（尾為主），提示改「描述最後得出/聊到什麼（落點）與整體」。取材純函式離線可測（尾段內容有進去）；LLM 注入。
2. **章節＝可注入 segment＋純正規化**：`FieldChat.segment(messages)` 呼叫 backend、`_parse_chapters` 解析、`normalize_chapters(raw, n)` 保證**範圍涵蓋全對話、不重疊、clamp**、失敗/過短→整段一章。stub 回確定性章節→離線可測。
3. **章節 on-demand 不落庫**：`POST /conversations/{cid}/segment` 即時算、渲染大綱（跳讀錨點）；不寫表、可重算。原則 6：先驗有沒有用，沒用就廢、零結構債。
4. **每章動作＝range 切片複用**：匯出端點加 `from/to`（切 `messages[from-1:to]` 再走 spec 024）；「整理這章」POST range→切片→`distill_factory`→既有候選/冊封頁（人閘門）。

## Project Structure

### Documentation (this feature)
```text
specs/027-conversation-recall/
├── plan.md · research.md · data-model.md · quickstart.md
├── contracts/recall.md
└── tasks.md（/speckit-tasks 產出）
```

### Source Code (repository root)
```text
src/learnnews/
├── chat/
│   ├── capture.py              # 【改】加 title_material(messages)＋normalize_chapters(raw, n)（純函式，零相依）
│   └── field_chat.py           # 【改】title() 改用 title_material＋落點提示；加 segment(messages)＋_parse_chapters
├── store/
│   └── repository.py           # 【改】rename_conversation(cid, title)->bool（UPDATE title）
└── web/
    ├── app.py                  # 【改】POST /conversations/{cid}/rename、/retitle、/segment、
    │                           #   /distill?from=&to=；conversation_export 加 from/to；segment_factory 注入點
    └── templates/
        ├── conversations.html  # 【改】每則加改名欄
        └── conversation.html   # 【改】改名/重新命名＋「整理成章節」＋章節大綱（跳讀＋每章匯出/整理鈕）

tests/unit/
├── test_capture_core.py        # 【擴】title_material（含尾段）／normalize_chapters（涵蓋/不重疊/clamp/退整段）
└── test_recall_web.py          # 【新】自動標題反映落點（注入）／手動改名／重生／切章渲染跳讀／每章 range 匯出／每章整理不自動冊封／退回不崩
```

**Structure Decision**: 沿用單一 web 專案。純核心進 `chat/capture.py`（與既有指紋/判準同家）；語意（title/segment）在 `field_chat.py`（可注入）；repo 加改名一法；web 加 5 路由（多為既有的擴充）。無新表、無新相依。

## Complexity Tracking

> 無違憲項。章節切分雖較投機，但以「on-demand 不落庫、輕量大綱、人觸發、可注入可測」控管——不引結構、可隨時廢。故不列複雜度豁免。
