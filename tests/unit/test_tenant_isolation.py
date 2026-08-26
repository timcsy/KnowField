"""spec 063（vision 階段 58）：B-底層——資料層變成多租戶。

⚠️ **這一支測試是整刀的重點，不是附屬品。**

漏一個 `owner_id` 條件，畫面上會出現**別人的知識**，而且**不報錯**
——看起來只像自己的資料變多了。而現有的 726 支測試全都是單人的，
它們**在漏掉過濾時照樣全綠**。⇒ 沒有這一支，這一刀等於沒有驗收。

判準：**能靠記性守住的東西，就是保證會漏的東西。**
所以這裡有兩層：
- `TestCrossTenantInvisible`：行為層——B 看不到 A 的任何東西
- `TestEveryQueryFilters`：掃描層——原始碼裡每一個碰到 owned 表的查詢都帶著條件
"""
import pathlib
import re
import unittest

from knowfield.store.repository import OWNED_TABLES, Repository
from tests.web_helpers import temp_db


class TestCrossTenantInvisible(unittest.TestCase):
    """行為層：兩個 owner，交叉可見度必須是 0。"""

    def setUp(self):
        self.db = temp_db()
        self.a = Repository(self.db, owner=1)
        self.b = Repository(self.db, owner=2)
        # A 的東西
        self.a_dom = self.a.create_domain("A 的領域", None)
        self.a_conv = self.a.save_conversation("A 的互動", [{"role": "user", "content": "a"}], None)
        self.a_why = self.a.add_why_node("A 的理解", [], [], False, 0, "2026-08-26")
        self.a.anoint_why_node(self.a_why)

    def tearDown(self):
        self.a.close(); self.b.close()

    def test_domains(self):
        self.assertEqual(self.b.list_domains(), [])
        self.assertIn("A 的領域", [d["name"] for d in self.a.list_domains()])

    def test_conversations(self):
        self.assertEqual(self.b.list_conversations(), [])
        self.assertTrue(self.a.list_conversations())

    def test_why_nodes(self):
        self.assertEqual(self.b.list_why_nodes("anointed"), [])
        self.assertTrue(self.a.list_why_nodes("anointed"))

    def test_corpus_is_not_shared(self):
        """⚠️ 最危險的一條：語料外洩＝**別人的理解在回答你的問題**，而畫面上毫無跡象。"""
        self.assertEqual(self.b._anointed_corpus_entries(), [])
        self.assertTrue(self.a._anointed_corpus_entries())

    def test_inventory(self):
        self.assertEqual(self.b._inventory_rows(), [])
        self.assertTrue(self.a._inventory_rows())

    def test_cannot_read_by_guessing_an_id(self):
        """知道 id 也拿不到——過濾不能只做在「列清單」那一層。"""
        self.assertIsNone(self.b.get_conversation(self.a_conv))
        self.assertIsNotNone(self.a.get_conversation(self.a_conv))

    def test_cannot_move_someone_elses_knowledge(self):
        """寫入面也要擋：B 不能把 A 的東西搬走。

        ⚠️ 搬去一個**跟現況不同**的領域——搬到 `None` 而它本來就是 `None` 的話，
        這支測試在過濾失效時也會綠（沒牙的斷言）。
        """
        b_dom = self.b.create_domain("B 的領域", None)
        self.a.set_knowledge_domain("conversation", self.a_conv, self.a_dom)
        self.b.batch_move([("conversation", self.a_conv)], b_dom)
        row = self.a.conn.execute(
            "SELECT domain_id FROM conversations WHERE id=%s", (self.a_conv,)).fetchone()
        self.assertEqual(row["domain_id"], self.a_dom, "B 把 A 的知識搬走了")


class TestEveryQueryFilters(unittest.TestCase):
    """掃描層：原始碼裡每一個碰到 owned 表的地方都要帶條件。

    ⚠️ 行為測試只驗**我想得到的**那些方法；這一支驗**全部**——
    包含明天才寫、而我不會回來補測試的那一個。
    """

    ROOT = pathlib.Path(__file__).resolve().parents[2]
    SRC = ROOT / "src/knowfield/store/repository.py"
    # ⚠️ 不只 repository.py——`app.py` 也直接下過 SQL，而那三句原本全都沒過濾。
    #    掃描器只掃它記得的檔案，就會給出**它自己都沒發現的**安全感。
    SOURCES = (SRC, ROOT / "src/knowfield/web/app.py")
    # 刻意豁免要寫成 `# owner-exempt: 理由`——把「我忘了」變成「我宣告了」
    EXEMPT = re.compile(r"#\s*owner-exempt:")
    # ⚠️ spec 067 起 owner 與 persona **共用同一個述詞**（`_own()`／`_OWN`）
    #    ⇒ 認得它就同時保住了兩者。這正是把兩個過濾收成一份寫法的報酬：
    #    隱私上線時**不需要再改一次那 88 個查詢點**。
    HAS_PREDICATE = re.compile(r"_OWN\b|_own\(|owner_id")

    def test_reads_and_writes_carry_the_owner_predicate(self):
        pat = re.compile(r"\b(?:FROM|UPDATE|INTO)\s+(" + "|".join(OWNED_TABLES) + r")\b")
        bad = []
        for f in self.SOURCES:
            lines = f.read_text(encoding="utf-8").split("\n")
            for i, line in enumerate(lines):
                if not pat.search(line):
                    continue
                window = "\n".join(lines[max(0, i - 3):i + 7])
                if self.HAS_PREDICATE.search(window) or self.EXEMPT.search(window):
                    continue
                bad.append(f"{f.name}:{i + 1}: {line.strip()[:90]}")
        self.assertEqual(bad, [], "這些查詢沒有帶 owner 條件：\n" + "\n".join(bad))

    def test_dynamic_table_names_also_filter(self):
        """⚠️ 掃描器原本有一個洞：`UPDATE {t}` 這種**動態表名**它看不見。

        而那不是理論問題——`set_knowledge_domain` 就是這樣寫的，
        於是 B 真的把 A 的知識搬走了，是行為測試抓到的。
        ⇒ 掃描器與行為測試**互相補洞**，兩支都要有。
        """
        lines = self.SRC.read_text(encoding="utf-8").split("\n")
        bad = []
        for i, line in enumerate(lines):
            if not re.search(r"\b(?:FROM|UPDATE|INTO)\s+\{", line):
                continue
            window = "\n".join(lines[max(0, i - 3):i + 7])
            if self.HAS_PREDICATE.search(window) or self.EXEMPT.search(window):
                continue
            bad.append(f"{self.SRC.name}:{i + 1}: {line.strip()[:90]}")
        self.assertEqual(bad, [], "這些動態表名的查詢沒有帶 owner 條件：\n" + "\n".join(bad))

    def test_scanner_actually_scanned_something(self):
        """⚠️ 掃到 0 行也會通過——先斷言分母不是零（spec 061 的教訓）。"""
        txt = self.SRC.read_text(encoding="utf-8")
        n = len(re.findall(r"\b(?:FROM|UPDATE|INTO)\s+(" + "|".join(OWNED_TABLES) + r")\b", txt))
        self.assertGreater(n, 40, f"只掃到 {n} 個查詢點——掃描器壞了")


if __name__ == "__main__":
    unittest.main()


class TestRootIsNotAmbiguous(unittest.TestCase):
    """`domain_id IS NULL` ＝ 根領域（階段 50 的裁決）。

    draft 原本擔心「多人之後 null 變歧義，所以每人要一棵**實體**根領域」。
    ⇒ 這一支測試檢查那個擔心還在不在：`(owner, NULL)` 已經是一個唯一的根，
    因為每一個查詢都帶 owner。**成立的話，實體根領域就是多餘的東西**（憲章 IV）。
    """

    def setUp(self):
        self.db = temp_db()
        self.a = Repository(self.db, owner=1)
        self.b = Repository(self.db, owner=2)

    def tearDown(self):
        self.a.close(); self.b.close()

    def test_two_owners_roots_do_not_mix(self):
        self.a.save_conversation("A 放在根", [{"role": "user", "content": "a"}], None)
        self.b.save_conversation("B 放在根", [{"role": "user", "content": "b"}], None)
        a_root = [i["label"] for i in self.a.domain_view(None)["items"]]
        b_root = [i["label"] for i in self.b.domain_view(None)["items"]]
        self.assertIn("A 放在根", a_root)
        self.assertNotIn("B 放在根", a_root)
        self.assertIn("B 放在根", b_root)
        self.assertNotIn("A 放在根", b_root)
