# Research：匯整分區（階段 14）

## R1：條目怎麼帶來源類別到首頁
- **決策**：`digest_entries` 加 `source_id TEXT DEFAULT ''`（`_migrate` ALTER 冪等，比照 source_class/
  ladder 先例）。`save_digest` 寫 `e.item.source_id`；`get_last_digest` 讀回填 `Item.source_id`。
  首頁用 `sources` 表 `id→type` 映射分類。
- **理由**：分類資訊源自「來源」；條目存 source_id、顯示時 join sources.type，最小新增、零改既有欄
  （教訓 8）。不在條目直接存「類別」是因為來源 type 可改（如重分類 HN），存 id 較穩。

## R2：分類規則（流 vs 吸引子）
- **決策**：`_section_of(source_type) → "foundational" if type in {"paper","blog"} else "news"`。
  未知 source_id（web 材料 source_id="web"、舊條目空）→ `type=None` → **新聞**（預設）。
- **理由**：concept——paper/基礎部落格＝常青吸引子；新聞媒體/社群/web 活水＝流。web 是流→新聞。

## R3：HN/Reddit 重分類 blog→news
- **決策**：`DEFAULT_SOURCES` 把 `hn-ai`、`reddit-localllama` 的 type 由 `blog` 改 `news`；並 upsert
  進使用者現有 db（覆蓋 type）。
- **理由**：HN/Reddit 是社群/新聞流、非基礎部落格；讓 `blog` 乾淨代表「基礎部落格」（ycc/lilianweng）。
  `upsert_source`（既有）以 id 覆蓋 → 直接改 type。

## R4：首頁分兩清單
- **決策**：`home` 取 `get_last_digest`（entries 帶 item.source_id）＋`list_sources`（id→type）；
  逐 entry 依 `_section_of` 分入 `news`/`foundational` 兩清單（各自 `entry_to_page`），傳模板。
  熱詞 chips／重整鈕在分區之上，不動。
- **理由**：純呈現層分組；不改匯整產生（FR-006）。

## R5：模板兩區
- **決策**：`digest.html` 兩個 section——「📰 今日新聞」列 news、「📚 基礎知識精選」列 foundational；
  **各區空則不渲染**（FR-004）。沿用既有 `_entry.html`。
- **理由**：空區不擺空殼；只啟用新聞源時就只顯示新聞區。

## R6：向後相容
- **決策**：舊 `digest_entries`（無 source_id，migrate 後為 ''）→ `type=None` → 新聞區。首頁照常、不崩（FR-005）。
- **理由**：ALTER 補欄預設 ''；未知一律落新聞，安全。
