# Quickstart：forward-pass 接每日流

## 前置
- 已有一份每日匯整（`/digest/refresh` 或 CLI 產生）。
- 已冊封至少一個吸引子（種子 `/ingest` 或已冊封根因 `/roots`），否則走「場空」提示。

## 驗證情境

### 1. 首頁匯整條目可關聯（FR-001／SC-001）
1. 開 `/`（首頁）。
2. 今日新聞區／基礎知識精選區每則卡片下方有「🧭 關聯到我的場」。
3. 對一則按下 → 導向結果頁：延伸/牴觸/成核/場空徽章＋grounded 理由＋連根因（與 `/library` 種子版一致）。

### 2. 排除自己（FR-003／SC-002）
- 若該條目本身也是種子（同 url），結果不會把它自己列為最近吸引子。

### 3. 按需、不自動（FR-004／SC-002）
- 首頁載入時**不**發生任何關聯呼叫（無外部請求）；只有點按鈕才跑。

### 4. 無 id 條目無鈕（FR-005／SC-003）
- `/pull`（即時深挖）頁的條目**不顯示**關聯按鈕。

### 5. 失敗友善（FR-006／SC-003）
- 判關係服務失敗 → 頁面不崩、繁中友善提示（沿用 spec 018）。

## 自動化測試（TDD）
```bash
uv run pytest tests/test_relate_flow.py -q          # 本增量新測
uv run pytest -q                                     # 全綠（現 286 → 不回歸）
```
涵蓋：`get_entry_material` 取種子/流/不存在；`get_last_digest` 帶 `entry_id`；`/field/relate` 吃流的
id＋排除自己＋失敗友善；`_entry.html` 有 id 顯鈕、pull 無鈕。
