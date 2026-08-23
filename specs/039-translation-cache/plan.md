# Implementation Plan: 翻譯落庫快取（階段 36）

**Branch**: `main`（小刀，不開分支）| **Date**: 2026-08-21 | **Spec**: [spec.md](./spec.md)

**Input**: `/specs/039-translation-cache/spec.md`；使用者當日重申「翻譯要可以自動保存」。

## Summary

翻譯完成後把譯文存進資料庫，同一份來源再要譯文時直接回快取（SC-001：< 2 秒，對照首次 63 秒）。
**快取以「內容雜湊」判新舊**（Assumptions：內容變了就失效，不用時間戳），
**逐翻譯單位保存**——降級的單位不存、同批成功的照存（FR-006，真跑後修訂），
**介面上零可見痕跡**（FR-003）。

技術取徑：新增一張 `translation_units` 表（**單位原文雜湊**為主鍵），在既有 SSE 路由
`GET /api/source/translate` 的最前面逐單位查快取、只翻沒命中的、在 `done` 之前寫回成功的。
前端一行都不動。

## Technical Context

**Language/Version**: Python 3.11（後端）；前端不動
**Primary Dependencies**: FastAPI、既有 `store.db`（SQLite/PG 雙後端，spec 036）
**Storage**: 新表 `translation_units`；`CREATE TABLE IF NOT EXISTS` → 兩種後端都自動遷移，無需 migration script
**Testing**: pytest（`tests/unit/`）
**Target Platform**: 既有 web service
**Project Type**: web（後端 only 這一刀）
**Performance Goals**: 全命中回應 < 2 秒（SC-001；實測 0.03 秒）
**Constraints**: 原文逐字不變（SC-003）；介面可見元素 0（SC-002）
**Scale/Scope**: 單使用者；來源數百份量級

## Constitution Check

| 原則 | 本刀怎麼過 |
|---|---|
| **I. TDD 不可妥協** | 每條 FR 先寫失敗測試再實作。⚠️ FR-006（降級不存）與 FR-004（內容變了失效）必須先看到紅燈——這兩條是「沉默失效」型，沒撞過的測試不知道自己在測什麼（`experience.md「一條沒有被錯誤實作撞過的測試，不知道自己在測什麼」`）。本刀對四條做了反向攻擊，全部成功撞紅 |
| **II. 繁體中文** | 規格、註解、commit 全繁中 |
| **III. 規格驅動** | spec → plan → tasks → implement，本檔即第二步 |
| **IV. YAGNI** | ⚠️ 主要壓力點。不做：跨來源共享、預先翻譯、命中率統計、手動清除。清理用「翻譯時順手掃一次」，**不引入排程器** |
| **V. 可觀測性** | 快取命中/寫入/清理各記一行 log（`_log`），但**不進使用者介面**（FR-003 只約束 UI，不約束 log） |
| **VI. 使用者保有決策主權** | 快取不改變任何使用者決定：按不按翻譯、看不看譯文都跟現在一樣。⚠️ 特別是**不自動顯示譯文**——見下 |

**沒有違規需要 justify。**

### ⚠️ 一個必須先釘死的讀法：「譯文立刻就在」＝ 按了立刻有，不是一開頁就是譯文

spec User Story 1 的 acceptance 寫的是「再次開啟**並要看譯文**，Then 譯文立即出現」。
⇒ 快取只讓**按下翻譯鍵**這件事變快，**不改變預設顯示的是原文**。

理由：自動顯示衍生物等於替使用者決定他要讀哪一版（違憲章 VI），
而且會讓「這頁現在是原文還是譯文」變成一個要猜的狀態。使用者這次說的是「自動**保存**」，不是「自動顯示」。

## Project Structure

### Documentation (this feature)

```text
specs/039-translation-cache/
├── spec.md
├── plan.md              # 本檔
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── checklists/
└── tasks.md             # /speckit-tasks 產出
```

### Source Code

```text
src/knowfield/
├── store/
│   ├── schema.py        # ＋ translation_units 表
│   └── repository.py    # ＋ get/save_translation_units、purge_stale_translations
├── text/
│   └── translate.py     # ＋ content_key()（純函式）、translate_stream 的 done 帶逐塊 ok
├── logging_setup.py     # ⚠️ handler 改掛套件根（見 D6）
└── web/
    └── app.py           # /api/source/translate：查快取 → 命中即回；未命中 → 翻完寫入

tests/unit/
├── test_translate.py            # ＋ content_key 的性質
├── test_translation_cache.py    # ＋ 落庫、部分命中、續命、清理
├── test_logging_reach.py        # ＋ 子 logger 的 INFO 到得了 handler（D6）
└── (contract) test_web_translate.py # ＋ 路由層：全命中、部分降級、順序、失效
```

**Structure Decision**: 沿用既有單一 Python 套件 ＋ `frontend/` 的既有結構。本刀**不動前端**——
這正是 FR-003（介面零痕跡）最強的實作保證：沒有前端改動，就不可能有快取相關的 UI。

## Phase 0：Research（決策與被否決的替代方案）

### D1. 用什麼判「內容變了」→ **每個翻譯單位原文的 SHA-256**

- **決定**：`content_key(unit)`；鍵是**內容**，不是位置（表裡沒有 url 欄）。
- **理由**：同一個字串既是翻譯輸入也是雜湊輸入，不會出現「雜湊算的跟翻的不是同一份」。
- **否決 A：時間戳比對**。編修內容不一定動時間戳，且 spec Assumptions 明寫以內容判定。
- **否決 B：只用 url 當鍵、不驗內容**。SC-004 要求 0% 拿到舊譯文，url 單鍵做不到。
- **⚠️ 否決 C（真跑後才推翻的原設計）：逐文件雜湊**。見 D3。

### D2. 清理放哪 → **每次翻譯請求順手掃一次**

- **決定**：進 `/api/source/translate` 時先 `purge_stale_translations`，門檻 **180 天未使用**。
- **理由**：FR-005 要求完全自動。翻譯是低頻動作，順手掃的成本可忽略，且**不需要排程器**（YAGNI）。
- **否決 A：排程 job**。為一張小表引入排程基礎設施，YAGNI。
- **否決 B：不清理**。FR-005 明文要求要有機制。

### D3. ⚠️ 降級怎麼辦 → **逐單位**：失敗的不存，成功的照存（真跑推翻了原設計）

- **原設計**：`failed > 0` ⇒ 整份一個字都不寫。理由是 FR-006 的原話「不把失敗固定下來」。
- **真跑推翻**：colah 那篇 45 個單位失敗 1 個（`API 連線失敗：read timed out`，暫時性）
  ⇒ 整份不存 ⇒ 使用者要的「自動保存」**根本不會發生**。
- **而且不是運氣**：N 個單位、單位失敗率 p，整份可存的機率是 (1-p)^N。
  N=45、p=2% ⇒ 約 40%。**逐文件保存在結構上就是脆弱的。**
- **決定**：逐單位。成功的存、失敗的永遠不進庫 ⇒ 下次一定重試。
  FR-006 的**理由**因此被更完整地滿足，而不是被放寬。
- 實測：113 秒 / 存 44 → 5.6 秒（只重翻 1 個）→ **0.03 秒**（全命中）。
- **⚠️ 逐塊成敗要由 `translate_stream` 明講**（done 事件帶 `ok` 陣列），
  **不能用「譯文 == 原文」去猜**——純程式碼／URL 的單位翻完本來就可能一樣。

### D4. 同一份同時被翻兩次 → **`ON CONFLICT(unit_key) DO UPDATE`**

- 兩次的 key 相同 ⇒ 原文相同 ⇒ 後寫覆蓋前寫無害。不加鎖（YAGNI）。

### D5. 快取存在但翻譯後端不可用 → **天然滿足，但要靠順序**

- 查快取排在 `make_translate_backend()` **之前**，所以後端掛掉不影響已快取的單位。
  ⚠️ 這要求的是**程式碼順序**，不是行為 ⇒ 需要一條專門釘順序的測試。

### D6. ⚠️ 真跑時才發現：降級日誌從來沒印出來過（憲章 V）

- `logging_setup.get_logger` 把 handler 掛在**傳進來的名字**上，而全專案只有
  `knowfield.web` 與 `knowfield.cli` 呼叫過它 ⇒ `knowfield.text.translate` 整條鏈上
  沒有 handler、`knowfield` 又是 NOTSET（吃 root 的 WARNING）⇒ **INFO 全被丟掉**。
- 後果：「第 N 塊退回原文（原因）」在正式執行時從來沒出現過，而那是診斷翻譯降級唯一的線索。
  我這次就是因為看不到它，才差點把暫時性網路逾時誤判成系統性的保護片段失敗。
- **修法**：handler 一律掛在套件根 `knowfield`，回傳要的子 logger。一次修好所有 `knowfield.*`，且不重複行。

## Phase 1：Design

### 資料

見 [data-model.md](./data-model.md)。

### 契約（既有路由的行為擴充，無新端點）

`GET /api/source/translate?u=<url>` — SSE，協定不變（`type` in data）。

| 情況 | 行為 |
|---|---|
| **全部單位命中** | **立即**送一則 `{"type":"done","total":N,"failed":0,"markdown":...}`，不送 `stage`，不建後端 |
| 部分命中 | 只翻沒命中的單位；`stage` 的分母 ＝ **真正還要做的量**，不是總單位數 |
| 全未命中 | 與現況逐字相同（並行翻譯＋`stage` 進度） |
| 任何一次翻完 | 把**翻成功的**單位寫入；降級的不寫 |
| 非英文／找不到來源 | 與現況逐字相同（`error`） |

⚠️ 全命中時**不送 `stage`**：前端的進度條靠 `stage` 驅動，沒有 stage 就不會閃一下進度再瞬間結束。

### quickstart

見 [quickstart.md](./quickstart.md)。

## Phase 1 後的 Constitution 重檢

- **IV. YAGNI**：最終落點是 1 張表、3 個 repository 方法、1 個純函式、1 個路由分岔、1 行 logging 修正。沒有排程器、沒有設定項、沒有前端改動。過。
- **VI. 主權**：預設顯示仍是原文；快取不改變任何使用者可見的選擇。過。
- **I. TDD**：D3、D5 兩條被特別標成「要先看紅燈」。過。

## Complexity Tracking

無違規。
