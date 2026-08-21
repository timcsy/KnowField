# 實作計畫：來源英→繁一鍵全文翻譯（階段 34 第二刀）

**Branch**: `038-source-translation` | **Date**: 2026-08-18 | **Spec**: [spec.md](./spec.md)

## Summary

英文來源整篇翻成繁中，使用者明確觸發、**並行 8 路**（實測 11.1 分 → 1.8 分）、SSE 回報實際進度。
沿用第一刀（spec 037）的承重保護與原文出口，**不做落庫快取**（先量再決定，YAGNI）。
與第一刀最大的性質差異：這是**生成式**的，所以「保護片段不完整就整塊退回原文」與
「明確標示 AI 翻譯」不是加分項，是必要條件。

## Technical Context

**Language/Version**: Python 3.12 · React 19（前端）
**Primary Dependencies**: 無新增（沿用既有 OpenAI 格式 chat 後端、stdlib `concurrent.futures`）
**Storage**: 不寫入。翻譯結果為暫態，不落地
**Testing**: pytest（現有 431 個 test 函式）
**Target Platform**: Linux 容器（prod）＋ macOS 本機
**Project Type**: Web service（FastAPI ＋ React）
**Performance Goals**: 125 塊 ≤ 2 分鐘（SC-002，實測 1.8 分）；進度至少每 10 秒前進
**Constraints**: 不寫回儲存層；承重片段逐字不變或整塊退回；後端不可用不得中斷
**Scale/Scope**: 單人；單篇來源（本機語料最長 125 塊 / 40k 字元）

## Constitution Check

*GATE：Phase 0 前必過，Phase 1 後複查。*

| 原則 | 評估 | 結果 |
|---|---|---|
| **I. TDD 不可妥協** | 核心（分塊、保護檢查、並行聚合、語言偵測）皆為純函式；LLM 呼叫走可注入的 backend，離線 stub 可測。 | ✅ |
| **II. 繁體中文文件** | spec/plan/research/tasks 全繁中。 | ✅ |
| **III. 規格驅動** | ⚠️ 本刀的設計前提**曾經是錯的**（「對照」），已由探針推翻並記入 `history/095`，spec 重寫後才動工——這正是本條要防的情況。 | ✅ |
| **IV. 簡潔與 YAGNI** | 零新相依；**刻意不做快取**（研究已量到 on-demand 足夠）；不另造並行/推播機制，沿用既有兩處形狀。 | ✅ |
| **V. 可觀測性與錯誤處理** | 單塊失敗降級為原文並計數；後端不可用回原文；不靜默吞例外。進度是 SSE 的 `stage`。 | ✅ |
| **VI. 使用者保有決策主權** | ⚠️ **本刀比第一刀吃重**：使用者現在主要看的是**生成物**。故（a）翻譯必須由人**明確觸發**、不自動；（b）必須標「AI 翻譯」；（c）必須能切回原文。三者缺一即違憲。 | ✅ 有條件 |

## Project Structure

### Documentation

```text
specs/038-source-translation/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/api-translate.md
├── checklists/requirements.md
└── tasks.md   （/speckit-tasks 產出）
```

### Source Code

```text
src/knowfield/text/
├── protect.py            # 既有（spec 037），不動
├── s2t.py                # 既有（spec 037），不動
├── lang.py               # 新增：CJK 佔比判語言（純函式）
└── translate.py          # 新增：分塊→並行→保護檢查→聚合（backend 可注入）

src/knowfield/web/app.py  # 新增 SSE 端點：翻譯進度 + 結果
frontend/src/pages/SourcePage.tsx   # 新增「翻成繁中」動作 + 進度 + AI 翻譯標示

tests/unit/test_text_lang.py        # 語言偵測
tests/unit/test_text_translate.py   # 保護檢查、單塊失敗降級、順序、並行聚合
tests/contract/test_web_translate.py# SSE 協定、原文出口、不寫回
```

**Structure Decision**：`translate.py` 與 `s2t.py` 並列於 `text/`——兩者都是顯示層文字處理，
共用 `protect`。翻譯的 LLM 呼叫走**注入的 backend**，讓核心邏輯（保護檢查、降級、聚合）
在零外呼下可測（experience：把重量級相依藏在可插拔介面後）。

## Complexity Tracking

| 項目 | 為何需要 | 為何不能更簡單 |
|---|---|---|
| SSE 進度端點 | 1.8 分鐘的等待沒有進度＝假 spinner（experience 明確反對） | 單一 JSON 回應 ⇒ 使用者對著沒反應的畫面等兩分鐘 |
| 保護片段完整性檢查 | 生成式模型不保證照規則；缺佔位符會**永久丟失**承重內容 | 直接 restore ⇒ 靜默吐出缺公式的譯文，比不翻更糟 |

**刻意不做**：落庫快取（研究已量到不需要）、對照 UI（已否決）、語言偏好設定。
