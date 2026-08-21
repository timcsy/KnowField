# Data Model：翻譯落庫快取（spec 039）

## 新表：`translation_units`

```sql
CREATE TABLE IF NOT EXISTS translation_units (
    unit_key TEXT PRIMARY KEY,
    markdown TEXT NOT NULL,
    last_used_at TEXT DEFAULT ''
);
```

| 欄位 | 意義 | 為什麼是這樣 |
|---|---|---|
| `unit_key` | **一個翻譯單位的原文**的 SHA-256 | FR-004／FR-008：內容變了 key 就不同 ⇒ 只有被改到的單位失效。⚠️ 不是譯文的雜湊，也不是整篇的雜湊 |
| `markdown` | 該單位的譯文 | 衍生物。⚠️ 絕不寫回 `digest_entries`／chunks（FR-002、FR-007） |
| `last_used_at` | 最後一次命中或寫入 | FR-005 清理的唯一依據 |

**沒有 `url` 欄**：鍵是內容不是位置。同一段文字出現在兩份來源，天然共用同一份譯文
——這不是刻意設計的「跨來源共享」（那條在 Out of Scope），是逐單位鍵的自然結果。

**型別遵守 spec 036 的 parity 原則**：日期一律 TEXT 存 ISO 字串，兩後端共用一份 DDL；
無自增主鍵 ⇒ 不需要 `SERIAL`／`INTEGER PRIMARY KEY` 分岔。

## ⚠️ 為什麼是逐單位，不是逐文件

第一版做的是逐文件（`source_translations`，url 主鍵 ＋ 整篇 content_key）。**真跑推翻了它**：

- colah 那篇切成 45 個單位，其中 1 個因 `API 連線失敗：read timed out` 降級。
- FR-006 說含降級的結果不得快取 ⇒ **整份不存** ⇒ 使用者要的「自動保存」不會發生。
- 而且這不是運氣：N 個單位、單位失敗率 p，整份可存的機率是 (1-p)^N。
  N=45、p=2% ⇒ 約 40%。**逐文件保存在結構上就是脆弱的。**

逐單位同時滿足兩邊：成功的存下（使用者要的），失敗的永遠不進庫（FR-006 的理由）。

## 不變式

1. **原文永不被本表影響**：本表只被 INSERT／UPDATE／DELETE，任何路徑都不寫回
   `digest_entries`、`entry_embeddings`（FR-002、FR-007）。
2. **命中即該單位的原文逐字相同**（雜湊相等）。
3. **只有翻譯成功的單位進得來**（FR-006）。

## Repository 介面

```python
def get_translation_units(self, keys: list[str], now: str) -> dict[str, str]
    """回 {unit_key: 譯文}，只含命中的；順手把命中的續命。"""

def save_translation_units(self, pairs: list[tuple[str, str]], now: str) -> None
    """寫入或覆蓋。⚠️ 呼叫端只能傳**翻譯成功**的單位。"""

def purge_stale_translations(self, before: str) -> int
    """刪除 last_used_at < before 的單位，回刪除數。完全自動、無介面（FR-005）。"""
```

⚠️ `get_translation_units` **順手續命**——分成兩個呼叫的話，路由層漏掉續命那步
會讓常用的單位被清掉，而那是**沉默**的（下次只是慢，不會報錯）。
