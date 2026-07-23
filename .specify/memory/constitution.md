<!--
Sync Impact Report
==================
版本變更: 1.0.0 → 1.1.0
變更類型: MINOR (新增一項核心原則)

修改的原則:
  - (新增) VI. 使用者保有決策主權
    理由：knowie 知識庫的「興趣畫像」設計引用「人保有決策主權」為依據，原憲章無此
    概念，形成概念死引用；正式納入憲章以修復（來源：/knowie-judge 一致性檢查）。

歷史版本 1.0.0（初始批准，MAJOR）建立的原則:
  - I. 測試優先開發（TDD，不可妥協）
  - II. 繁體中文文件與溝通
  - III. 規格驅動開發
  - IV. 簡潔與 YAGNI
  - V. 可觀測性與明確錯誤處理

新增章節:
  - 核心原則 (6 項)
  - 額外限制
  - 開發流程與品質關卡
  - 治理

移除章節: 無

需要同步的範本:
  - ✅ .specify/templates/plan-template.md (Constitution Check 為通用引用，無需修改)
  - ✅ .specify/templates/spec-template.md (無 constitution 專屬引用)
  - ✅ .specify/templates/tasks-template.md (無 constitution 專屬引用)

延遲項目 / TODO: 無
-->

# LearnNews 專案憲章

## 核心原則

### I. 測試優先開發（TDD，不可妥協）

所有功能程式碼 MUST 遵循測試驅動開發流程：先撰寫測試 → 確認測試失敗（Red）→
撰寫最小可用實作使測試通過（Green）→ 重構（Refactor）。禁止在沒有對應失敗測試的
情況下撰寫新的功能程式碼。每個 Pull Request MUST 包含涵蓋新增或變更行為的自動化測試。

理由：測試優先能鎖定需求、避免回歸、並讓重構安全進行。此為本專案不可妥協的基石。

### II. 繁體中文文件與溝通

所有規格文件、設計文件、任務清單、以及與使用者的回答 MUST 使用繁體中文撰寫。
技術術語與程式碼識別字（函式名、變數名、指令）MAY 保留原文。程式碼註解 SHOULD
使用繁體中文，但 API 慣例名稱與外部相容性所需的英文除外。

理由：明確統一的語言能降低溝通成本、確保團隊與使用者對規格的理解一致。

### III. 規格驅動開發

每項功能 MUST 先有經過批准的規格（spec）與實作計畫（plan），才進入實作。實作
MUST 可追溯回規格中的具體需求；當實作與規格產生分歧時，MUST 先更新規格再修改
程式碼，而非反向調整。

理由：規格是唯一事實來源，確保工作可驗收、可審查、且範圍受控。

### IV. 簡潔與 YAGNI

設計 MUST 從最簡方案開始，僅在有明確且當前的需求時才引入抽象、相依套件或架構
複雜度（YAGNI）。任何額外複雜度 MUST 在計畫的複雜度追蹤中提出理由。

理由：過早的複雜化會拖慢開發並增加維護成本；簡潔的系統更容易測試與理解。

### V. 可觀測性與明確錯誤處理

系統 MUST 產生結構化且可讀的日誌以利除錯。錯誤 MUST 被明確處理並回報清晰、
可行動的訊息，禁止靜默吞掉例外。面向使用者的錯誤訊息 MUST 使用繁體中文。

理由：可觀測性與清楚的錯誤回報是快速定位問題與維持系統可靠度的前提。

### VI. 使用者保有決策主權

系統中影響使用者所見的行為（例如推播內容、興趣過濾、排序）MUST 讓使用者保有
最終控制權：可檢視、可修改、可覆寫。AI／自動化 MAY 提議與學習校準，但 MUST NOT
在使用者不知情或無法否決的情況下主導決策。

理由：LearnNews 的使用者是重度自我加工型讀者，工具的職責是分診而非代替思考；
把「餵什麼給我」的主權交還使用者，才符合根信念——降低成本而不剝奪判斷。

## 額外限制

- 版本控制 MUST 採用語意化版本（Semantic Versioning，MAJOR.MINOR.PATCH）。
- 相依套件 MUST 保持最小化；新增第三方相依 MUST 在計畫中說明必要性。
- 破壞性變更 MUST 在文件中標註，並提供遷移說明。

## 開發流程與品質關卡

- 每個 Pull Request MUST 通過所有自動化測試後才能合併。
- 每個 Pull Request MUST 經過至少一位審查者審查，並確認符合本憲章各項原則。
- 品質關卡（測試通過、規格對齊、繁中文件完整）MUST 在合併前全部滿足。
- 違反原則的例外情形 MUST 在計畫的複雜度追蹤中記錄理由並取得批准。

## 治理

本憲章為本專案所有其他開發實務的最高準則；當實務與憲章衝突時，以憲章為準。

- 修訂本憲章 MUST 透過 Pull Request 提出，說明變更內容與理由，並經審查批准。
- 版本遞增規則：MAJOR 用於不相容的治理／原則移除或重新定義；MINOR 用於新增
  原則或實質擴充指引；PATCH 用於釐清、措辭或錯字修正等非語意變更。
- 所有 Pull Request 與審查 MUST 驗證是否符合本憲章。
- 本憲章的合規性 MUST 於每次審查中檢視；發現的偏差 MUST 記錄並修正或取得例外批准。

**Version**: 1.1.0 | **Ratified**: 2026-07-23 | **Last Amended**: 2026-07-23

<!-- Knowie: Project Knowledge -->
## Project Knowledge

This project maintains structured knowledge in `knowledge/`:

- **Principles** (`knowledge/principles.md`): Core axioms and derived development principles — the project's non-negotiable rules.
- **Vision** (`knowledge/vision.md`): Goals, current state, architecture decisions, and roadmap.
- **Experience** (`knowledge/experience.md`): Distilled lessons from past development — patterns, pitfalls, and takeaways.

Read these files at the start of any task to understand the project's *why* and constraints.
Additional context may be found in `knowledge/concepts/`, `knowledge/history/`, and `knowledge/draft/`.

Learned procedures live in `knowledge/skills/` (agentskills.io SKILL.md format). If your tool auto-loads skills, they may be projected into your skill directory; otherwise read the relevant `SKILL.md` there and follow it.
<!-- /Knowie -->
