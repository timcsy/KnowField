# 實作計畫：文章進 `/chat` 的視野（階段 37）

**Branch**: `041-article-in-chat` | **Date**: 2026-08-21 | **Spec**: [spec.md](./spec.md)

## Summary

在 `/chat` 讓使用者**明確選一篇**已生成的文章帶進這輪脈絡，沿用既有 `sources` 的**分層注入**形狀
（`field_chat.py:214-231` 已在分「你收藏的＝外部證言，比核心理解軟」），文章當**第三層、更軟**
——它是**從地基長出來的衍生物**。

**核心約束不是功能，是閘門**：文章以**臨時 system 訊息**注入，**不進 `history`**
⇒ `distill`（蒸餾冊封候選）的輸入只由 `history` 串成，**結構上看不到文章**。

## Technical Context

**Language**: Python 3.12 ＋ React 19 · **Dependencies**: 無新增
**Storage**: 唯讀（讀 `articles`），不寫入 · **Testing**: pytest（484）＋ vitest（13）
**Constraints**: 未選文章時脈絡逐字不變；bare 模式不注入；注入有長度上限

## Constitution Check

| 原則 | 評估 | 結果 |
|---|---|---|
| I. TDD | 注入組裝是純函式（`_messages`），可直接斷言送出的訊息內容 | ✅ |
| II. 繁中文件 | 全繁中 | ✅ |
| III. 規格驅動 | spec 先行；⚠️ 且本刀的設計前提**當天被更正過一次**（主要情形是「腦力激盪」不是「改文章」），更正記在 draft | ✅ |
| IV. YAGNI | 零新相依、沿用既有注入形狀與由來機制；不做 Canvas／段落級出處 | ✅ |
| V. 可觀測性 | 選到已刪文章 → 明確告知，不靜默略過 | ✅ |
| VI. 決策主權 | ⚠️ **本刀最吃重**：人**明確選**才帶（不自動）；文章標明為 AI 產物、不得蓋過核心理解；冊封候選結構上不由文章生成 | ✅ |

## Project Structure

```text
src/knowfield/chat/field_chat.py   # _messages 加「文章層」注入（第三層、最軟）
src/knowfield/web/app.py           # /api/chat/stream 收 article_id；讀文章傳入
frontend/src/ChatPage.tsx          # 選文章帶入（明確動作）＋顯示「已帶：<標題>」
frontend/src/lib/api.ts            # streamChat 帶 article_id

tests/unit/test_field_chat_article.py    # 注入分層、bare 不注入、長度上限、未選時逐字不變
tests/contract/test_chat_article.py      # 端點帶 article_id；⚠️ distill 輸入不含文章（SC-003）
```

**Structure Decision**：注入點放在 `_messages()` ——它是**組裝送出訊息**的地方，
而 `history` 是**另一條路徑**（客戶端送、也是 `distill` 的輸入）。兩者不相交**就是那條結構保證**，
不需要新機制。

## Complexity Tracking

| 項目 | 為何需要 | 為何不能更簡單 |
|---|---|---|
| 文章自成一層（不塞進 sources） | 可信度不同層：sources 是外部證言，文章是**自家衍生物**；混層會讓 AI 拿自己的產物回敬使用者 | 塞進 sources ⇒ 分不出來，直接違反 US2 |

**刻意不做**：Canvas、段落級出處、多篇、自動挑選。
