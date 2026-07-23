# 來源 Adapter 介面契約

每個來源（arXiv、HF Papers、Semantic Scholar、newsletter…）實作同一介面，讓
去重／排序／摘要與具體來源解耦。新增來源＝新增一個 adapter，不動核心（YAGNI／可測試）。

## 介面

```
SourceAdapter:
    name: str
    type: "paper" | "news" | "blog"

    def fetch(since: datetime) -> list[Item]
        """取得自 since 以來的條目。MUST 回傳含非空 url 的 Item；
           無法取得時 raise SourceUnavailable（由呼叫端記入 missing_sources，不靜默）。"""
```

## 契約（所有 adapter 必守）
- **回傳的每個 Item MUST 有非空 `url`（直達原文）**——無原文連結者不得回傳（FR-006）。
- `external_id` MUST 穩定且可用於精確去重（arXiv ID／DOI／guid）。
- `title` 非空；`abstract`、`published_at`、`lang` 盡力填入。
- 失敗（逾時／達用量上限／解析錯誤）MUST 明確拋出 `SourceUnavailable`，附繁中原因；
  **不得**回傳部分髒資料或靜默吞掉（原則 V）。
- MUST 尊重來源 robots／服務條款與速率限制；Semantic Scholar 須指數退避（research.md R1）。

## 契約測試（`tests/contract/`）
- 以**錄製的來源樣本**（fixtures）驗證 `fetch` 解析出正確的 Item 欄位。
- 注入失敗回應 → 驗證拋出 `SourceUnavailable`，且不回傳半成品。
- 驗證回傳 Item 皆有非空 `url`。
- 測試**不打真實外部 API**（確定性、離線）。

## MVP 需實作的 adapter
- `ArxivAdapter`（arxiv_api）
- `HFPapersAdapter`（hf_papers）
- `SemanticScholarAdapter`（semantic_scholar，含退避）
- `RssAdapter`（rss／email-ingestion 產生的 Atom feed 共用）— 承載 1–2 個精選新聞源
