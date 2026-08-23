"""場的使用審計——唯讀，攤開「哪些功能有消費者」。

走 Repository（雙後端 adapter，history/086），所以本機 SQLite 和 prod PG 都跑得動。
只 SELECT。要看才跑，不常駐。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from knowfield.store.repository import Repository  # noqa: E402


def q1(repo: Repository, sql: str) -> int:
    row = repo.conn.execute(sql).fetchone()
    if not row:
        return 0
    return int(list(row.values() if hasattr(row, "values") else row)[0] or 0)


def main() -> None:
    dsn = os.environ.get("KNOWFIELD_DATABASE_URL") or "knowfield.db"
    kind = "prod PG" if dsn.startswith("postgres") else "本機 SQLite"
    repo = Repository()
    print(f"資料來源：{kind}（{dsn.split('@')[-1] if '@' in dsn else dsn}）")
    print("=" * 66)

    # 每列＝（階段, 功能, 製造動作, 消費動作）
    rows = [
        # 每段對話都先被自動暫存（spec 028），所以「製造」＝全部對話；
        # 「消費」＝人按過『升永久』的。別用 temporary=1 當分母——那只是「還沒衰減掉的」。
        ("23", "對話暫時存檔",
         q1(repo, "SELECT count(*) FROM conversations"),
         q1(repo, "SELECT count(*) FROM conversations WHERE temporary=0"),
         "被自動暫存過的對話", "人按過升永久的（唯一證明暫存有用的動作）"),
        ("18", "對話的『由來』綁根因",
         q1(repo, "SELECT count(*) FROM conversations"),
         q1(repo, "SELECT count(*) FROM conversations WHERE why_node_id IS NOT NULL"),
         "對話總數", "綁到根因的（階段 18 的殺手級路徑）"),
        ("22/29", "對話章節切分",
         q1(repo, "SELECT count(*) FROM conversations"),
         q1(repo, "SELECT count(*) FROM conversations WHERE chapters IS NOT NULL"
                  " AND chapters<>'' AND chapters<>'[]'"),
         "對話總數", "有章節骨架的"),
        ("10/17", "核心理解（根因）冊封",
         q1(repo, "SELECT count(*) FROM why_nodes"),
         q1(repo, "SELECT count(*) FROM why_nodes WHERE conversation_id IS NOT NULL"),
         "冊封的根因", "從對話長出來的（迴圈有沒有閉）"),
        ("28", "認識論層次（kind）",
         q1(repo, "SELECT count(*) FROM why_nodes"),
         q1(repo, "SELECT count(*) FROM why_nodes WHERE kind IS NOT NULL AND kind<>''"),
         "根因總數", "有標層次的"),
        ("30", "高證實文章輸出", 0,
         q1(repo, "SELECT count(*) FROM articles"), "—", "產出的文章"),
        # spec 044：帶入物的由來。⚠️ 在這一刀之前，37/38 的使用量在儲存層**零痕跡**
        # ——041 FR-003 刻意不讓帶入物進 messages（對的），結果報告上的空白
        # 分不出「沒人用」和「量不到」。這兩列就是把那個空白換成數字。
        ("37", "帶著文章聊",
         q1(repo, "SELECT count(*) FROM conversations"),
         q1(repo, "SELECT count(*) FROM conversations WHERE carried_kind='article'"),
         "對話總數", "帶著文章開的"),
        ("38", "帶著來源聊",
         q1(repo, "SELECT count(*) FROM conversations"),
         q1(repo, "SELECT count(*) FROM conversations WHERE carried_kind='source'"),
         "對話總數", "帶著來源開的"),
        ("36", "翻譯落庫快取", 0,
         q1(repo, "SELECT count(*) FROM translation_units"),
         "—", "存下來的譯文單位（>0 代表真的有人翻過）"),
        # ⚠️ 這列曾是「階段 8 來源訂閱」，報出 15/0（0%）——那是**工具在說謊**，不是功能沒人用：
        # 拉模式隨 history/068 退役，`digest` 子指令已不存在，`last_fetch_at` 全專案零處寫入，
        # 那 15 筆是空庫時 `app.py:85` 自動塞的。比照「每日匯整」改標為殘骸存量（history/107）。
        ("退役", "來源訂閱（拉模式，history/068 已退役）", 0,
         q1(repo, "SELECT count(*) FROM sources"),
         "—", "自動種進去的來源（沒有任何抓取路徑，不該當使用率讀）"),
        # 這列是「殘骸偵測」不是消費率：分診已退役（history/068），數字只該是歷史存量。
        ("退役", "每日匯整（分診，history/068 已退役）", 0,
         q1(repo, "SELECT count(*) FROM digests"),
         "—", "殘留的匯整批次（退役後不該再長）"),
        ("未接", "behavior_signals（儀器）", 0,
         q1(repo, "SELECT count(*) FROM behavior_signals"),
         "—", "行為訊號（產品程式碼零呼叫，見 next brief）"),
    ]

    silent = []
    for stage, name, made, used, made_label, used_label in rows:
        ratio = "—" if not made else f"{used / made:.0%}"
        mark = "🔴" if used == 0 else ("🟡" if made and used / max(made, 1) < 0.2 else "🟢")
        print(f"\n{mark} [階段 {stage}] {name}")
        if made:
            print(f"     製造：{made:5d}  {made_label}")
        print(f"     消費：{used:5d}  {used_label}" + (f"   （消費/製造 {ratio}）" if made else ""))
        if used == 0:
            silent.append(f"[階段 {stage}] {name}")

    print("\n" + "=" * 66)
    if silent:
        print("消費者為 0 的功能：")
        for s in silent:
            print(f"  🔴 {s}")
        print("\n⚠️ 0 不等於該砍。先問「它想解的需求是什麼、正確的維度是哪一條」")
        print("   （experience：一個沒人用的功能，多半是把旋鈕裝在錯的軸上）。")
    else:
        print("每個功能都有消費者。")
    if kind == "本機 SQLite":
        print("\n⚠️ 這是本機 dev 資料，不是使用證據。真實使用要對 prod 跑。")
    print("\n⚠️ 帶入物由來（階段 37/38）只從 spec 044 出貨後才開始記——"
          "在那之前建立的對話一律為空，那是**沒資料**，不是**沒人用**。")
    repo.close()


if __name__ == "__main__":
    main()
