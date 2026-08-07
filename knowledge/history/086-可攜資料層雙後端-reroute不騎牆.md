# 086：可攜資料層 adapter——本地 SQLite ＋ prod PG（re-route「不騎牆」）

> 日期：2026-08-07。**決策轉移（re-route）**。設計源 `draft/2026-08-07-本地SQLite與prod-PG雙後端`；
> spec/plan `specs/036-portable-db-adapter/`；promote vision 階段 33（使用者 /goal 做完＝commit）。承 `history/084`。

## 轉移：從「全部 PG 不騎牆」到「本地 SQLite＋prod PG 雙後端」
**舊**（`history/084`，同日稍早）：全部 PG、**別做雙後端**（怕 drift、投機抽象、parity 稅）。**前提＝本地跑得起 PG。**
**新**：加薄 dialect adapter，**本地 SQLite（零 server）＋prod PG**。
- **為何 re-route**：使用者澄清真痛＝**本地不想跑任何 server**（Docker 怪、也不想跑原生 PG）。local-PG（原生/Docker）
  都是 server，打不到；**SQLite 是唯一零-server 的 SQL 庫**（PG 無成熟嵌入式）。「不騎牆」的前提被這需求推翻。
- **大方認**：committed route 前提變了就改，並留因果（本篇）。全部 PG 遷移本身沒白做——它仍是 **prod substrate**，
  SQLite 只加在本地。

## 為何這次雙後端站得住（當初反對＝drift，已機械消除）
- 本地 dev/測試跑 SQLite（**1.83s、零 server、零 Docker**——解使用者痛）；`KNOWFIELD_TEST_BACKEND=postgres` 同套測試跑 PG。
- **兩後端各 352 綠**＝drift 被機械抓、非靠祈禱。這才是「一份可攜資料層、兩邊都驗過」，不是騎牆賭運氣。

## 做法：薄 adapter（非 SQLAlchemy）
- `store/db.py connect(url)`：`postgres(ql)://`→psycopg（dict_row）；其餘→sqlite3（Row）。`_Conn` 薄包裝：sqlite 時
  `%s`→`?`（SQL 無字面 %，安全）；row 兩後端皆支援 `r["c"]`/`r.keys()`/`dict(r)`。
- schema `init_db` 依 `conn.dialect` 分岔自增型別（`SERIAL`↔`INTEGER PRIMARY KEY`）；其餘 DDL 共用（RETURNING/ON CONFLICT
  SQLite 3.49.1 皆支援）。repository SQL **本體不動**。**零新相依**（sqlite3 stdlib）。

## 順修的 bug（值得記，且是好教訓）
- **測試讀了開發者本機 `.env`**：`Config.from_env` 的 `load_dotenv(".env")` 把使用者剛填好的**真實 auth 設定**撈進測試
  → auth 門鎖被啟用 → 全部 web 測試被擋（症狀：POST 被 401→讀空 IndexError、autosave 無 temp_id KeyError、
  export 302→登入 redirect loop TooManyRedirects）。**一度被誤判成 SQLite parity 問題**，實為測試隔離漏洞
  （PG 那輪 352 綠是因為當時 .env 還沒填 auth）。修：`tests/conftest.py` 設 `KNOWFIELD_NO_DOTENV=1`＋清 auth/DB env；
  `Config.from_env` 尊重旗標。→ 升 experience。

## 已知邊界
pgvector 是 PG-only（SQLite 無向量索引）；本階段**不含** pgvector；未來檢索升級時該功能 PG 專屬、SQLite 走純 Python 降級。

## 產物
spec/plan `specs/036-portable-db-adapter/`；commit `326469c`（實作，兩後端各 352 綠）。
`history/084` 的「不做雙後端」scope 守門已標 superseded → 本篇。draft 反流退場。
