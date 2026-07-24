---
name: evaluate-and-add-source
description: 為 LearnNews 評估並加入一個新的新聞/論文來源——實測可用性、挑穩定高訊號的、加進預設來源、驗證供料、反流 history。當要新增或替換來源（RSS 電子報、部落格、論文 API）時使用。
---

# 評估並加入來源（LearnNews）

重複做過多次（history/005、006、007，及拉模式的 arXiv search）：每次都是「實測 → 挑 →
加 → 驗 → 反流」。此技能把它固化，避免每次重造。

**為什麼存在**：來源名冊會變動；每次憑感覺加來源容易加到雜訊源或掛掉的源。先實測、
再加、留因果，才穩。對齊根公理「跟上趨勢的成本要極低」——來源要準、穩、可溯源。

## 步驟

### 1. 實測候選端點的可用性（別憑感覺）
對每個候選 URL 跑一段 stdlib 探測（**只用標準函式庫，零安裝**）：

```python
import urllib.request, urllib.error, time, re
cands = { "名稱": "URL", ... }
for name, url in cands.items():
    t = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LearnNews/0.1"})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8", "replace")
        n = len(re.findall(r"<item\b|<entry\b", body))
        kind = "RSS" if "<item" in body else ("Atom" if "<entry" in body else "?")
        print(f"  OK {name}: {r.status} {kind} {n} 篇 ({time.time()-t:.1f}s)")
    except urllib.error.HTTPError as e:
        print(f"  X {name}: HTTP {e.code}")
    except Exception as e:
        print(f"  X {name}: {type(e).__name__}")
```

### 2. 挑選標準（訊噪比 > 量）
- **200 OK、低延遲、有內容**（item/entry 數合理）。
- **高訊號**：AI 專門策展電子報（Import AI、Last Week in AI）、官方部落格、品質新聞
  （Ars Technica AI）優先；通用搜尋（Google News）雜訊多，**避免**。
- **免金鑰、法遵**：公開頁／官方 feed；尊重 robots/ToS。**Semantic Scholar free search
  持續 429，別當預設**（見 history/005）。

### 3. 加進預設來源
在 `src/learnnews/cli/fetchers.py` 的 `DEFAULT_SOURCES` 加一列：
```python
Source("<id>", "<顯示名>", "<paper|news|blog>", "<arxiv_api|hf_papers|rss|email_ingest>",
       "<endpoint>"),
```
新聞/部落格/電子報一律用 `rss`（RssAdapter 同時吃 RSS 2.0 與 Atom）。

### 4. 驗證供料
跑一次匯整（離線即可）確認新源進池、`missing_sources` 不含它：
```bash
LEARNNEWS_BACKEND=offline uv run learnnews --db /tmp/probe.db digest --limit 6
```
確認測試仍綠：`uv run pytest -q`。

### 5. 反流（留因果）
在 `knowledge/history/` 新增一筆轉移檔（舊名冊 → 新名冊、為什麼變、實測數據；體例見
history/005–007）；若取代舊源，在舊 history 標「已被 NNN 取代」（record transitions, don't
delete）。來源盤點的研究背景見 `episodes/2026-07-23-競品與來源研究快照.md`（唯來源**現況**
以 `DEFAULT_SOURCES`＋history 為準，episode 是當時快照、不追更）。

## 完成準則
- 新源實測 200 且高訊號；已加進 DEFAULT_SOURCES；匯整驗證供料、測試綠燈；history 留下轉移。
