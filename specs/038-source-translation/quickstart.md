# Quickstart：驗證來源英→繁翻譯

## 1. 測試（憲章 I：先紅後綠）

```bash
uv run pytest tests/unit/test_text_lang.py tests/unit/test_text_translate.py -q
uv run pytest tests/contract/test_web_translate.py -q
uv run pytest -q          # 全部，零回歸（基準：431）
```

## 2. 跑起來看（用 run-knowfield skill）

```bash
KNOWFIELD_AUTH_DISABLED=1 uv run uvicorn 'knowfield.web.app:create_app' --port 8000
cd frontend && npm run dev      # 讀它印出來的 port
```

⚠️ 改完後端**必須重啟**，並 `ps aux | grep -c "[u]vicorn knowfield.web.app"` 確認舊的死了。

開到英文來源：Lil'Log〈What are Diffusion Models?〉（125 塊，本機語料最長的一篇）。

## 3. 要親眼確認的（測試抓不到的那些）

- [ ] 「翻成繁中」動作**只在英文來源出現**（中文來源不該有）
- [ ] 進度數字**真的在動**（不是假 spinner）——SC-003 至少每 10 秒
- [ ] 完成時間 **≤ 2 分鐘**（SC-002；序列基準 11.1 分）
- [ ] 數學公式在譯文裡**正常渲染**——單元測試看字串，使用者看渲染結果
- [ ] 畫面上有**「AI 翻譯」標示**，且能切回英文原文（憲章 VI，缺了就違憲）
- [ ] 逐詞讀一段譯文（experience：整段通順、錯的只有一兩個詞，掃過去只會覺得「好像對」）

## 4. 驗不寫回

```bash
# 翻譯前後比對儲存層逐字相同（C-003）
```
