# Implementation Plan：來源直接對話（階段 38）

**Branch**: `main`（小刀）| **Date**: 2026-08-21 | **Spec**: [spec.md](./spec.md)

## Summary

`/source` 頁一個動作 → 開新對話、來源當第一則（形狀沿用 spec 041），
並把**原文**注入模型脈絡，**不依賴撒網是否命中**。長來源以「開頭 ＋ 份內檢索 ＋ 明講節錄」處理，
不截斷。帶入的來源要與撒網結果**去重**。

## Technical Context

**Language/Version**: Python 3.11 ＋ React 19（前端沿用 041 的元件）
**Primary Dependencies**: FastAPI、既有 `rag.service.retrieve_corpus`、`store.repository`
**Storage**: 無新表——來源與其塊都已在 `digest_entries`
**Testing**: pytest（unit ＋ contract）；前端 vitest 不需新增（沿用 041 元件）
**Performance Goals**: 注入不得讓首 token 明顯變慢（份內檢索走既有 embedding 快取）
**Constraints**: 脈絡長度上限；原文逐字不變；未帶來源時脈絡逐字相同
**Scale/Scope**: 單來源 20k–38k 字量級

## Constitution Check

| 原則 | 本刀怎麼過 |
|---|---|
| **I. TDD** | 每條 FR 先紅。⚠️ FR-003（不依賴撒網）與 FR-007（去重）是沉默失效型 —— 兩條都要反向攻擊 |
| **II. 繁中** | 全繁中 |
| **III. 規格驅動** | vision 階段 38（人 commit）→ spec → plan → tasks |
| **IV. YAGNI** | ⚠️ 主壓力點。不新增表、不新增檢索機制、**不重開形狀討論**、不傳「使用者現在看哪一版」的參數 |
| **V. 可觀測性** | 注入時記一行：全文／節錄、份內檢索命中數、去重掉幾條 |
| **VI. 主權** | 人明確按才帶入；預設不變 |

## Phase 0：Research

### D1. 注入內容 → **儲存層原文**，且無條件告知「你看到的可能是轉換後的版本」

- 譯文是 AI 產物，餵回去是回灌線的縮小版；餵原文則讓模型能**替使用者抓翻譯的失真**。
- **否決：傳一個 `sview` 參數說明使用者當下看哪一版**。多一條前後端管線、而且可能傳錯；
  無條件講一句永遠為真的話達成同一目的（YAGNI）。

### D2. 長來源 → **開頭 ＋ 份內檢索 ＋ 明講節錄**，不截斷

- **否決：`[:CAP]` 硬切**（spec 041 對文章就是這樣做的）。後半消失而使用者不知道 ⇒ 沉默失敗。
  ⚠️ 這是**刻意不沿用**母設計的一處，理由寫在 FR-005。
- **份內檢索**＝`list_corpus_entries()` 依 url 過濾後走既有 cosine 排序。
  來源的每個塊就是一列 `digest_entries`，所以「份內檢索」不需要新機制。
- **保留整體成分**：開頭 N 字一定進，否則「這篇整體在講什麼」答不出來。
- **節錄要明講**：脈絡裡寫「本份共 M 段，此處為開頭 ＋ 與問題最相關的 j 段」，
  模型才不會把沒看到的當作不存在。

### D3. 選內容放路由、分層放 `field_chat` → 兩邊都測得到

- 路由拿 repo／embedder 做選段；`field_chat._messages` 只負責分層措辭。
- 沿用 `article` 的形狀：路由組好一個 dict 傳進去。

### D4. 去重 → **以 url 比對，丟掉撒網結果中的同一份**

- `sources` 每條有 `.url`；帶入的來源也有 url。相等就丟。
- ⚠️ 不能只靠「模型自己會看出重複」——它不會，它會把同一段當兩個獨立佐證。

### D5. 冊封閘門 → **不照搬 spec 041 FR-003**

- 041 的閘門擋 model collapse，前提是文章＝AI 產物。來源是一手素材，
  且 `/api/source/distill` 早就允許從來源冊封。
- ⇒ 來源**照 `article` 的做法**只出現在臨時訊息、不進 `history`（那是脈絡衛生，不是閘門），
  但**不宣稱**任何「候選不得源自來源」的保證——那條對來源不成立也不需要。

## Phase 1：Design

### 契約

`GET /chat/stream`（既有）新增可選參數 `source_url`：

| 情況 | 行為 |
|---|---|
| 有 `source_url` 且非 bare | 取該來源原文 → 全文或節錄 → 以**一手素材**層注入；撒網結果中同 url 者丟棄 |
| 無 `source_url` | 與現況**逐字相同** |
| bare | 不注入（FR-008） |

前端：`/source` 頁一顆「💬 帶著這份聊」→ `/?source=<url>&stitle=<標題>`，
`ChatPage` 沿用 041 的 article 分支（開新對話、第一則、`<details>`）。

### 資料

無新表。

## Complexity Tracking

無違規。
