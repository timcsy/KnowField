# Quickstart：驗收翻譯落庫快取（spec 039）

前置：`uv sync`；`.env` 已設 LLM 後端；伺服器啟動見 `knowledge/skills/run-knowfield/SKILL.md`。

## 1. 自動化驗收

```bash
uv run pytest tests/unit/test_repository.py -k translation -q
uv run pytest tests/unit/test_web_source_translate.py -q
uv run pytest -q            # SC-005：既有測試零回歸
```

## 2. 真跑驗收（SC-001）

⚠️ 驗證必須走**與正式路徑完全相同的管線**（`experience.md「驗證要走與正式路徑完全相同的管線，否則照出來的是驗證腳本的 bug」`）——用瀏覽器，不要用自寫腳本。

1. 開一份**英文**來源的 `/source?u=…`，按 **🌐 翻成繁中**，記下耗時（首次，數十秒）。
2. **重新整理**該頁，再按一次 **🌐 翻成繁中**。
   - **期望**：譯文幾乎瞬間出現（SC-001 < 2 秒），且**進度條不閃**（命中不送 `stage`）。
   - **期望**：兩次的譯文內容相同。
3. 按 **看轉換前**／切回原文 → 原文與收進當時逐字相同（SC-003）。

## 3. FR-003 驗收（介面零痕跡）

走遍 `/source` 頁所有可見元素，**找不到**任何與快取有關的字樣或動作
（沒有「已快取」標記、沒有「重新翻譯」、沒有「清除快取」）。
本刀不動 `frontend/`，所以這條的最強證據是 `git diff --stat` 裡沒有前端檔案。

## 4. FR-004 驗收（內容變了不給舊譯文）

在 DB 裡改動該來源的任一 chunk（或重新收進），再按翻譯 →
**期望**：重新翻譯（有進度條），不是秒回舊譯文。
