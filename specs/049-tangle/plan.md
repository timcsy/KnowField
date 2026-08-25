# 實作計畫：整理與糾纏（階段 44）

**Spec**: [spec.md](spec.md) · **Created**: 2026-08-25

## 技術脈絡

| | |
|---|---|
| 後端 | Python / FastAPI ／ `store/repository.py` 雙後端（SQLite ＋ Postgres） |
| 前端 | React ＋ TypeScript ／ `pages/DomainsPage.tsx` |
| 前置 | 階段 43 的 `domains` 表與 `conversations.domain_id`（spec 048） |

## 憲章檢查

- **I. TDD** — 測試先行；⚠️ 每條「沉默失敗」的斷言都要被**故意寫錯的實作**打紅過（見下）。
- **III. 規格驅動** — FR-004／005 的護欄直接對應到兩個對抗測試。
- **IV. YAGNI** — 不做多重歸屬、不做 undo、不做拖放。
- **VI. 使用者保有決策主權** — 糾纏是問句不是規則（FR-008）。

## 階段

### 階段 0：加欄（沿用 spec 044 的宣告式路徑）

`schema.py` 的 `_ADD_COLUMNS` 加三筆：`articles.conversation_id`、`articles.domain_id`、`why_nodes.domain_id`；
新表 `article_roots(article_id, why_node_id, layer)`。⚠️ `_ensure_columns` 是**懶跑**的
（第一次建 `Repository` 才補），不是行程啟動就補。

### 階段 1：文章的來源連結（P1，先補斷線）

- `output/article.py::generate_article` 回傳 `used_body_ids` / `used_ext_ids`
  ——⚠️ **不動 kind-split 那幾行**（那是階段 42 剛校準過的排序）。
- `save_article(..., root_ids, ext_ids, conversation_id)`；讀回用 `article_roots(aid)`。

### 階段 2：搬動與糾纏偵測（P1）

`repository.py`：

```
_KIND_TABLE = {"conversation": …, "why_node": …, "article": …}
knowledge_domain / set_knowledge_domain
_neighbours(kind, kid)          # 一跳，不是閉包
tangles_for(kind, kid, new_domain)   # 相鄰且領域「不同且非空」
move_knowledge(kind, kid, new_domain, bring_along=False)
```

### 階段 3：路由

- `POST /api/knowledge/{kind}/{kid}/tangles` — **純預覽，零副作用**（FR-003）
- `POST /api/knowledge/{kind}/{kid}/move` — `bring_along` 決定連帶

### 階段 4：介面

`DomainsPage` 每段對話一個「搬到…」下拉（**排除現在所在的領域**）；
偵測到糾纏就展開琥珀色提示塊：列出會被拆散的項目 ＋ 三個按鈕 ＋ 一行「連帶只走一層」的但書。

## ⚠️ 測試紀律：攻擊要真的打得到

本專案吃過三種**攻擊沒落地**的虧：測試沒有牙／攻擊是 no-op／**攻擊打到另一條程式路徑**。
所以 FR-004、FR-005 各配一個對抗測試，而且**必須先看它變紅**：

- 把 `_neighbours` 改成傳遞閉包 → 護欄測試要紅
- 把「連帶」改成遞迴 → 只走一層的測試要紅

## 被否決的做法

- **搬動時自動連帶全部** → 破 FR-008，且會搬走半個場。
- **糾纏當錯誤擋下來** → 糾纏是知識庫的**正常結構**（DAG 的邊），不是要修的東西。
- **傳遞閉包偵測** → 見 spec 的護欄表：66/75 條連著對話，實測即廢。
