# Quickstart：驗證來源簡體正規化

## 前置

```bash
uv sync                      # 會裝上新增的 opencc-python-reimplemented（可選相依）
```

引擎為**可選**：未安裝時所有測試仍應通過（走 identity fallback），只是轉換不生效。

## 1. 跑測試（憲章 I：先紅後綠）

```bash
uv run pytest tests/unit/test_text_protect.py tests/unit/test_text_s2t.py -q
uv run pytest tests/contract/test_web_source_s2t.py -q
uv run pytest -q                     # 全部，確認零回歸（基準：369 個 test 函式）
```

**預期**：全綠，且總數 > 369。

## 2. 驗承重保護（本功能的主風險）

六個危險案例來自 [research.md](./research.md) 的實測，每個都必須逐字不變：

| 案例 | 必須不變的部分 |
|---|---|
| 程式碼區塊 | `def 处理(内存):` 內的識別字 |
| 裸 URL | `http://a.cn/发展/index.html` |
| 圖片 | `pic1.zhimg.com/发展_v2.jpg` |
| 數學區塊 | `$$…\text{发展}$$` |
| 行內數學 | `$x_{发}$` |
| 行內程式碼 | `` `发送` `` |

⚠️ 若其中任何一項在轉換後改變，**本功能淨值為負**，不得出貨。

## 3. 對真實來源驗（端到端）

已知的簡體來源：知乎〈深入解析Flow Matching技术〉

```bash
uv run uvicorn knowfield.web.app:create_app --factory --port 8000 &
curl -s 'localhost:8000/api/source?u=https://zhuanlan.zhihu.com/p/685921518' | python3 -c "
import json,sys; d=json.load(sys.stdin)
print('套用轉換:', d.get('s2t_applied'))
print(d['markdown'][:300])"
```

**預期**：`s2t_applied: true`，正文為繁體，`技术` 顯示為 `技術`。

驗原文可取回（FR-005 / 憲章 VI）：

```bash
curl -s 'localhost:8000/api/source?u=…&raw=1' | python3 -c "…"   # 應為簡體原文
```

## 4. 驗引擎缺席不炸（SC-005）

```bash
uv run --no-project python -c "…"    # 或暫時移除套件
```

**預期**：詳情頁仍可開啟、回 200、顯示原文、`s2t_applied: false`。

## 5. 驗延遲（SC-003）

比較 `raw=1` 與 `raw=0` 的回應時間，差值應 < 200ms。

## 6. 人工確認（憲章 VI）

在前端開啟該來源，確認：
- 預設看到繁體
- **有一個切換能看回原文**——沒有它，這個功能違反憲章 VI
