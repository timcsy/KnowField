# 介面契約：來源翻譯

## `GET /api/source/translate`（SSE）

以 Server-Sent Events 回報進度與結果，**沿用 `/chat/stream` 既有協定**：每行 `data: {...}`，
事件型別放在 payload 的 `type` 欄（不是 `event:` 行）——與 `web/app.py:37` 的 `_sse()` 一致。

### 請求

| 參數 | 型別 | 說明 |
|---|---|---|
| `u` | string | 來源 URL |

### 事件

| `type` | 其餘欄位 | 時機 |
|---|---|---|
| `stage` | `done`, `total`, `failed` | 每完成一塊 |
| `done` | `markdown`, `total`, `failed` | 全部完成 |
| `error` | `message` | 無法開始（來源不存在、非英文來源） |

### 契約條件

- **C-001**：`done` 的 `markdown` 塊數 MUST 等於原文塊數。
- **C-002**：翻譯失敗的塊 MUST 以**原文逐字**出現在結果中，並計入 `failed`。
- **C-003**：翻譯 MUST NOT 修改儲存層——呼叫前後 `get_source_chunks(u)` MUST 逐字相同。
- **C-004**：後端不可用 MUST 回 `error` 或全部降級的 `done`，MUST NOT 拋出未處理例外。
- **C-005**：對非英文來源，端點 MUST 回 `error`（FR-009）；前端據 `/api/source` 的語言旗標先行隱藏動作。

## `GET /api/source` 既有端點的增補

| 欄位 | 型別 | 說明 |
|---|---|---|
| `is_english` | bool | **新增**。CJK 佔比 < 3%。前端據此決定顯不顯示「翻成繁中」動作 |

既有欄位（含 spec 037 的 `s2t_applied`、`raw`）語義 MUST 不變。

## 內部契約：`knowfield.text`

```
lang.is_english(text) -> bool
    CJK 佔比 < 0.03

translate.translate_chunks(chunks, backend, max_workers=8) -> list[TranslatedChunk]
    不變式：
      - len(結果) == len(chunks)，順序一致
      - 任一塊的 backend 失敗或保護片段不完整 → 該塊 text 逐字等於原文、ok=False
      - backend 為 None（不可用）→ 全部原樣回傳、ok=False
      - 不呼叫任何儲存層
```
