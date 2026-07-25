# Contract：根因萃取

## `RootCauseExtractor.extract(title, body) -> Candidate`（`rootcause/extract.py`）
- `StubExtractor`：回確定性 `Candidate`（claim 非空、touchstones 全 `passed=False`＝待驗、
  `no_material=False`）；零外部呼叫。
- `OpenAIExtractor`：`_post` chat 抽根因＋逐條試金石自評＋霧詞旗標；解析 JSON。呼叫/解析失敗
  → 拋 `SourceUnavailable`（路由攔）。抽不出 → `no_material=True`。
- **MUST** 對自己 adversarial（system 明令逐條反駁、只用材料、不杜撰）。

## `make_root_cause_extractor(config)`（`backends/factory.py`）
- openai＋key → `OpenAIExtractor`，否則 `StubExtractor`。

## Repository（`store/repository.py`）
- `add_why_node(...)->id`（candidate）；`list_why_nodes(status=None)`；`anoint_why_node(id, claim=None)`；
  `delete_why_node(id)`（清負 id 嵌入）。
- `list_corpus_entries` UNION `status='anointed'` → `CorpusEntry(entry_id=-id, source_class="root", …)`。

## Web（`web/app.py`）
- `POST /whynode/extract`（`entry_id`＝種子）：呼叫 extractor；`no_material` → 友善提示、不建候選；
  否則 `add_why_node`（候選）→ 導 `/roots`。失敗（`SourceUnavailable`）→ 友善繁中、不 500。
- `POST /whynode/anoint`（`id`＋可選 `claim`）→ `anoint_why_node` → 導 `/roots`。
- `POST /whynode/remove`（`id`）→ `delete_why_node` → 導 `/roots`。
- `GET /roots`：列**候選**（claim＋試金石逐條 badge＋霧詞旗標＋證據連結＋冊封/退回）與**已冊封**。
- `GET /library`：每則種子加「萃取根因」鈕。
- 面向使用者全繁中；候選明標「AI 推斷（據 [來源]）」。

## 契約測試（離線、零外部呼叫）
1. `StubExtractor.extract` 回 `Candidate`（claim 非空、touchstones 7 條、no_material=False）。
2. `OpenAIExtractor`（注入 poster 回 JSON）→ 解析 claim/touchstones/fog/no_material；poster 拋 → `SourceUnavailable`。
3. repository：`add_why_node`→`list_why_nodes('candidate')` 有它；`anoint_why_node`→ 進 `list_corpus_entries`
   （source_class='root'、負 id）；`delete_why_node` → 消失且嵌入清掉。
4. `_weight('root') > _weight('explainer') > 1.0`。
5. **閉環**：add→anoint 一個 why-node（claim 含關鍵詞）→ `RagService.answer(問該關鍵詞)` 檢索得到它
   （sources 含其證據 url）。
6. `/whynode/extract`（注入 stub extractor）→ 候選入庫、導 `/roots`、頁面顯示 claim＋試金石。
7. `/whynode/anoint` → status 轉 anointed；`/whynode/remove` → 消失。
8. 萃取失敗（extractor 拋 `SourceUnavailable`）→ `/whynode/extract` 友善繁中、非 500、不建候選。
9. `no_material` 萃取 → 不建候選、友善提示。
10. `/library` 每則種子有「萃取根因」鈕；`/roots` 分「候選 / 已冊封」。
