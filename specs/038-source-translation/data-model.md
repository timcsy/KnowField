# Phase 1 資料模型

## 不新增資料表、不新增欄位

翻譯結果**不落地**（spec Assumptions：先做並行、量完再決定快取）。以下皆為記憶體中的暫態型別。

## 暫態型別

### TranslatedChunk

| 欄位 | 型別 | 說明 |
|---|---|---|
| `index` | int | 在原文塊序列中的位置。聚合時據此還原順序 |
| `text` | str | 譯文；**降級時為原文** |
| `ok` | bool | 是否成功翻譯（承重片段完整、後端未失敗） |

**不變式**

- 聚合後的塊數 MUST 等於輸入塊數（不多不少）。
- `ok=False` 時 `text` MUST **逐字等於**該塊原文——降級是退回原文，不是輸出殘缺品。
- 順序 MUST 與輸入一致（沿用 `ex.map` 的性質，不靠 index 排序也成立，但 index 保留供回報）。

### TranslationProgress

| 欄位 | 型別 | 說明 |
|---|---|---|
| `done` | int | 已完成塊數 |
| `total` | int | 總塊數 |
| `failed` | int | 降級為原文的塊數 |

供 SSE `stage` 事件回報（FR-003）。**不落地**。

## 保護片段完整性判準

```
masked, segments = protect.mask(chunk)
translated = backend(masked)
完整 ⟺ 對每個 i，placeholder(i) 都出現在 translated 中
```

不完整 → 整塊退回原文（`ok=False`）。**不嘗試修補**——位置錯的公式比沒翻更糟（research 決策 3）。

## 語言判定

```
CJK 佔比 = len(CJK 字元) / len(全文)
英文來源 ⟺ 佔比 < 0.03
```

閾值來自探針掃語料的實測（三篇英文來源皆 0.0%，中文來源 > 15%）。
FR-009 據此決定要不要提供翻譯動作。
