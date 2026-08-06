# CLI 指令契約：knowfield

MVP 的對外介面。每個指令為一個契約，測試以 `tests/contract/` 驗證其輸入/輸出與退出碼。
面向使用者文字皆繁中（FR-010）。錯誤以非零退出碼＋繁中可行動訊息回報，不靜默（原則 V）。

## `knowfield digest`
產出當日匯整（核心，US1）。

- **輸入**：`--date YYYY-MM-DD`（預設今日）、`--limit N`（預設 15，SC-007）、
  `--format terminal|markdown`（預設 terminal）、`--output PATH`（可選）。
- **行為**：取得 → 去重 → 興趣過濾排序 → 對進榜條目生成封頂摘要 → 輸出匯整。
- **輸出**：有序條目清單，每則含「定位（一句）／為何值得看（一句）／直達原文連結」。
  結尾標示 `missing_sources`（缺漏來源）與 `truncated_count`（未納入則數）。
- **退出碼**：0＝成功（含空匯整，須明確標示 is_empty）；非 0＝致命錯誤（如設定缺失）。
- **契約測試**：
  - 給定含跨源重複的樣本 → 同一事件只出現一次（FR-002）。
  - 每則輸出都有非空的原文連結（FR-006、SC-003）。
  - 每則摘要 ≤ 兩句（SC-004）。
  - 某來源不可取得 → 匯整照常產出並列於 `missing_sources`（FR-011）。
  - 無符合條目 → 退出碼 0 且標示空匯整（Edge Case）。

## `knowfield interests`
管理興趣清單（US2、FR-008/009；憲章原則 VI）。

- **子指令**：
  - `list`：顯示目前生效的明講主題清單。
  - `add <topic>`：新增明講主題。
  - `remove <topic>`：移除主題（使用者明講優先於學習推斷）。
  - `set <topic...>`：以給定清單**覆寫**全部。
- **行為**：變更即時持久化，次日/下次 `digest` 生效（SC-005）。
- **契約測試**：add/remove/set 後 `list` 反映變更；被 remove 的主題不因學習權重復活
  （明講優先）。

## `knowfield sources`
檢視／啟用來源（維運用）。

- **子指令**：`list`（顯示來源與 `last_status`）、`enable/disable <id>`。
- **契約測試**：`disable` 後該來源不參與 `digest`。

## 全域約定
- `--json` 旗標：以 JSON 輸出（供程式化使用與測試斷言）；預設人類可讀繁中。
- 所有錯誤訊息繁中、指出可行動的下一步（原則 V）。
