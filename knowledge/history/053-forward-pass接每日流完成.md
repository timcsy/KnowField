# 053：forward-pass 接每日流（階段 15 增量 b）完成

> 日期：2026-07-26　｜　承接 history/052（promote 增量 b）

## 轉移
vision 階段 15 增量 b **由「已 commit」→「已完成」**。spec 019 按 TDD 實作完：首頁每則**匯整條目**
（新聞＋基礎兩區）加「🧭 關聯到我的場」→ 複用階段 15 `FieldRelate` 引擎跑 forward pass。
測試 **286→298**（新增 `tests/contract/test_relate_flow.py` 12 測）、零回歸。commit `1ecd9c4`。
**真後端（OpenAI＋Tavily）在每日流條目上跑通**——grounded 判關係、誠實回「無明顯關聯」（不硬掰）。

## 為何是它（護城河接到最該作用的流）
北極星習慣「讀 delta／把新東西接到你的模型」最該作用在**剛炸的新聞**，非已存種子。階段 15 只做在
種子＝護城河只碰了已存的；增量 b 把**同一引擎**接到每日流，才真正兌現北極星。concept
「理解一則新材料＝一次前向傳遞」（有吸引子的場 :97）——**新材料正是每日流**，不只種子。

## 關鍵設計（三接點、零新相依/零新表/不改引擎）
- **種子與流同住 `digest_entries`**（種子在 SEEDS_DATE 容器）→ 新增 `get_entry_material(id)→
  (headline_or_title, body, url)|None`，**以 id 直取一列，一路徑同時服務種子與流**；`/field/relate`
  用它取代 `list_seeds` 專找種子。library 種子鈕零改動自動續用（種子亦一列）。
- **暴露條目 id**：`DigestEntry+=entry_id`，`get_last_digest` SELECT `de.id` 帶出；`PageEntry+=entry_id`，
  `entry_to_page` 用 `getattr`（DigestEntry 有→帶出；**PullEntry 無→None**）。
- **模板一次生效**：`_entry.html` 加 `{% if e.entry_id %}` 關聯鈕；`digest.html` 兩區共用該片段故一改
  兩區都有，**pull 頁條目無 id 故自然無鈕**（FR-005 免分模板）。
- **排除自己**：`FieldRelate` 既有 `exclude_url`，路由傳該條目 url。
- **原則 5 續守**：relate **不寫任何庫**（同 spec 018），流的條目路徑一樣只提關係、人決定。

## 產物
- `models/__init__.py`（DigestEntry+entry_id）、`store/repository.py`（get_last_digest 帶 id、
  `get_entry_material`）、`web/views.py`（PageEntry+entry_id、entry_to_page getattr）、
  `web/app.py`（/field/relate 泛化）、`templates/_entry.html`（關聯鈕）。
- 測試：`tests/contract/test_relate_flow.py`（12）。規格：`specs/019-relate-flow/`。

## 出口
- 階段 15 增量 b 完成。`轉向場的護城河` draft：設計 A 完成、其「接到每日流」延伸亦完成（本增量）。
  draft 不刪（設計 B 收進捕捉、近親場驅動來源推薦仍孵化）。
- 後續（同北極星缺口，未 commit）：關聯**搜尋結果**（/search）、多跳 forward pass、批次成核、
  場驅動來源推薦（北極星 #2）、回訪複利（北極星 #3）。
