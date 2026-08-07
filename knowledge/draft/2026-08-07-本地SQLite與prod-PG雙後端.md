# 本地 SQLite ＋ prod PG：可攜資料層（re-route「全部 PG 不騎牆」）

> 狀態：**draft／設計提案（thinking-line）**。日期：2026-08-07。
> 怎麼冒出來的：階段 31 剛把資料層全部遷到 PG（`history/084`、`e7dcbec`），使用者隨即提「本地還是想支援 SQLite」。
> 追問後真正的痛＝**「不想在本地跑任何 server」**（Docker 最近怪怪的、也不想跑原生 PG server）。
> 母概念：資料層 substrate（承 `history/084` 全部 PG 的續集/修正）。

## re-route：為何回頭改「不騎牆」
- **當初決策**（`history/084`）：全部 PG、**不做雙後端**（怕 drift、投機抽象、parity 稅）。**前提假設＝本地跑得起 PG。**
- **前提被推翻**：使用者要**本地零 server**。而 local-PG（原生或 Docker）**都是 server**，打不到這需求。
  **SQLite 是嵌入式檔案庫、in-process、沒有 server 進程**——Python 生態裡「零 server 的 SQL 庫」實際上只有它（PG 無成熟嵌入式）。
- ∴ 「不騎牆」在「本地零 server」這個當初沒被充分權衡的需求下，值得 re-route。**大方認：committed route 前提變了。**

## 關鍵：drift 這個主要反對，可機械消掉
當初最重的反對＝「本地綠、prod 不一定綠」。解法：
- **本地 dev＋本地測試跑 SQLite**（零 server、零 Docker、快）——**完全解使用者的痛**。
- **CI＋prod 跑 PG**（CI testcontainers、prod 真 PG）。
- **同一套測試在兩後端都跑**（後端由 env 選）→ **drift 當場被抓，不靠祈禱**。
- 核心 DB-less 測試維持零安裝（不變）。
→ 這不是「騎牆賭運氣」，是「**一份可攜資料層、兩邊都驗過**」。

## 做法（傾向：薄 adapter，非完整 SQLAlchemy）
- 現況好消息：剛寫的 PG SQL **已幾乎可攜**——現代 SQLite 也支援 `RETURNING`（3.35+）、`ON CONFLICT`（3.24+）。
- 真正差異只有：**佔位符（`%s` vs `?`）、driver/連線、row→dict、schema 自增型別（`SERIAL` vs `INTEGER … AUTOINCREMENT`）**。
- ∴ **薄 dialect adapter**（一個小模組：依 URL scheme 選 sqlite3/psycopg、統一佔位符與 dict row、schema 自增分岔）就能收口，
  **SQL 本體幾乎不動**。比重寫成 SQLAlchemy Core 輕得多。
- **SQLAlchemy Core** ＝更重、更正統的替代；本案用不到那麼重（除非日後 query 複雜度爆增再考慮）。

## 邊界／代價（誠實記）
- **pgvector 未來是 PG-only**（SQLite 無向量索引）→ 檢索升級 pgvector 時，該功能 PG 專屬、SQLite 本地走降級（純 Python cosine，即現況）。可接受，先講明。
- **一次性 repository 再改**（改成走 adapter）＋一點 schema 兩方言維護。
- **測試矩陣**：整合測試要能在兩後端跑（本地 SQLite／CI PG）——`tests/pgtest.py` 的 temp_db 依 env 選後端。

## 出口
- **✅ 已 promote → `vision.md` 階段 33（2026-08-07，使用者 commit /goal 做完）**。SQLite 3.49.1 實測 RETURNING/ON CONFLICT OK。
  本 draft＝其 in-flight 設計理由，動工完成才反流退場。
- acceptance（已進 vision 階段 33）：本地 SQLite 零 server 可跑 app＋測試、CI/prod PG、**同套測試兩後端皆綠**、行為零回歸、核心 DB-less 測試不變。
- **這 supersede `history/084` 的「不騎牆」立場**（動工時 `history/084` 標該段 superseded、開新 history 記 re-route 因果）。
- 相關：`history/084-全部PG-資料層遷移定案`、`specs/034-postgres-migration/`、
  experience「加全域行為用設定存在性當開關」（同型：後端由 env/URL scheme 選）。
