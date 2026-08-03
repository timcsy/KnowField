"""spec 025：收料純核心——內容指紋（去重識別）＋收尾缺口判準。離線、缺項不崩。
spec 026：既有重複清理計畫 plan_dedupe。"""

import unittest

from learnnews.chat.capture import (
    cheap_title,
    conversation_fingerprint,
    distill_gap,
    expired_temp_ids,
    normalize_chapters,
    plan_dedupe,
    title_material,
)


def _m(tag):
    return [{"role": "user", "content": tag}]


class TestFingerprint(unittest.TestCase):
    def test_same_content_same_fp(self):                    # T002
        m = [{"role": "user", "content": "q"},
             {"role": "assistant", "content": "a"}]
        self.assertEqual(conversation_fingerprint(m), conversation_fingerprint(list(m)))

    def test_different_content_differ(self):                # T002
        a = [{"role": "user", "content": "q1"}]
        b = [{"role": "user", "content": "q2"}]
        self.assertNotEqual(conversation_fingerprint(a), conversation_fingerprint(b))

    def test_order_matters(self):                           # T002
        a = [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}]
        b = [{"role": "assistant", "content": "y"}, {"role": "user", "content": "x"}]
        self.assertNotEqual(conversation_fingerprint(a), conversation_fingerprint(b))

    def test_empty_stable(self):                            # T002
        self.assertEqual(conversation_fingerprint([]), conversation_fingerprint([]))
        self.assertIsInstance(conversation_fingerprint([]), str)

    def test_missing_content_ok(self):                      # T002 缺欄位不崩
        fp = conversation_fingerprint([{"role": "assistant"}])
        self.assertIsInstance(fp, str)

    def test_ignores_sources(self):                         # T002 忽略易變欄
        a = [{"role": "assistant", "content": "a", "sources": [{"url": "u1"}]}]
        b = [{"role": "assistant", "content": "a", "sources": [{"url": "u2"}]}]
        self.assertEqual(conversation_fingerprint(a), conversation_fingerprint(b))


class TestDistillGap(unittest.TestCase):
    # 用 min_total=8、gap=6 做例（實作可用不同預設；這裡顯式傳參）
    def test_long_and_uncaptured_returns_range(self):       # T003
        self.assertEqual(distill_gap(20, 4, 8, 6), (5, 20))

    def test_short_none(self):                              # T003 太短不吵
        self.assertIsNone(distill_gap(5, 0, 8, 6))

    def test_just_captured_none(self):                      # T003 剛收滿→缺口不足
        self.assertIsNone(distill_gap(20, 18, 8, 6))

    def test_gap_exactly_threshold(self):                   # T003 邊界：等於門檻→提醒
        self.assertEqual(distill_gap(14, 8, 8, 6), (9, 14))

    def test_last_captured_none_or_negative_as_zero(self):  # T003
        self.assertEqual(distill_gap(10, None, 8, 6), (1, 10))
        self.assertEqual(distill_gap(10, -3, 8, 6), (1, 10))

    def test_nonpositive_total_none(self):                  # T003
        self.assertIsNone(distill_gap(0, 0, 8, 6))
        self.assertIsNone(distill_gap(-1, 0, 8, 6))


class TestPlanDedupe(unittest.TestCase):
    def test_groups_survivor_repoint(self):                 # T001
        # A 組（同內容）id 1,2,3；B 組 id 4,5；單份 id 6
        convos = [{"id": 1, "messages": _m("A")}, {"id": 2, "messages": _m("A")},
                  {"id": 3, "messages": _m("A")}, {"id": 4, "messages": _m("B")},
                  {"id": 5, "messages": _m("B")}, {"id": 6, "messages": _m("C")}]
        prov = {10: 1, 11: 3, 12: 4, 13: 6}   # 10→loser,11→survivorA,12→loserB,13→單份
        plan = plan_dedupe(convos, prov)
        self.assertEqual(plan.n_groups, 2)
        self.assertEqual(sorted(plan.delete_ids), [1, 2, 4])   # 各組非最大
        self.assertEqual(plan.n_extra, 3)
        self.assertEqual(plan.repoint, {10: 3, 12: 5})         # loser→survivor；survivor/單份不變
        self.assertEqual(plan.n_roots, 2)

    def test_no_dup_empty_plan(self):                       # T001
        convos = [{"id": 1, "messages": _m("X")}, {"id": 2, "messages": _m("Y")}]
        plan = plan_dedupe(convos, {5: 1, 6: 2})
        self.assertEqual(plan.delete_ids, [])
        self.assertEqual(plan.repoint, {})
        self.assertEqual((plan.n_groups, plan.n_extra, plan.n_roots), (0, 0, 0))

    def test_empty_convos(self):                            # T001
        plan = plan_dedupe([], {})
        self.assertEqual((plan.n_groups, plan.n_extra, plan.n_roots), (0, 0, 0))

    def test_extra_without_root_still_deleted(self):        # T001 未連根因的多餘份仍刪
        convos = [{"id": 1, "messages": _m("A")}, {"id": 2, "messages": _m("A")}]
        plan = plan_dedupe(convos, {})     # 無任何根因連結
        self.assertEqual(plan.delete_ids, [1])   # 留 2、刪 1
        self.assertEqual(plan.repoint, {})       # 無重指

    def test_different_content_not_grouped(self):           # T001 異指紋不入計畫
        convos = [{"id": 1, "messages": [{"role": "user", "content": "65 句版"}]},
                  {"id": 2, "messages": [{"role": "user", "content": "70 句版"}]}]
        plan = plan_dedupe(convos, {})
        self.assertEqual(plan.delete_ids, [])   # 內容不同→不併


class TestTitleMaterial(unittest.TestCase):
    def test_tail_is_included(self):                        # T001 尾段有進（解「凍在第一句」）
        msgs = ([{"role": "user", "content": "開頭主題A " * 300}]      # 大量開頭
                + [{"role": "assistant", "content": "落點結論B_四元樹影片串流"}])  # 結尾落點
        mat = title_material(msgs, head_chars=600, tail_chars=1600)
        self.assertIn("落點結論B_四元樹影片串流", mat)       # 尾段落點有進取材
        self.assertIn("開頭主題A", mat)                      # 首段也在

    def test_short_returns_whole(self):                     # T001 短→全取
        msgs = [{"role": "user", "content": "短"}]
        self.assertIn("短", title_material(msgs))

    def test_empty_and_missing(self):                       # T001 空/缺不崩
        self.assertEqual(title_material([]), "")
        self.assertIsInstance(title_material([{"role": "user"}]), str)


class TestNormalizeChapters(unittest.TestCase):
    def test_cover_no_overlap(self):                        # T002 涵蓋不重疊
        raw = [{"title": "一", "start": 1, "summary": "s1"},
               {"title": "二", "start": 5, "summary": "s2"}]
        ch = normalize_chapters(raw, 10)
        self.assertEqual([(c["start"], c["end"]) for c in ch], [(1, 4), (5, 10)])

    def test_out_of_order_overlap_clamp(self):              # T002 亂序/越界/重疊→修正
        raw = [{"start": 5}, {"start": 1}, {"start": 100}]  # 亂序＋越界
        ch = normalize_chapters(raw, 10)
        self.assertEqual([(c["start"], c["end"]) for c in ch], [(1, 4), (5, 9), (10, 10)])
        # 涵蓋 [1,10]、不重疊
        self.assertEqual(ch[0]["start"], 1)
        self.assertEqual(ch[-1]["end"], 10)

    def test_first_forced_to_one(self):                     # T002 首章補到 1
        ch = normalize_chapters([{"start": 3}], 8)
        self.assertEqual((ch[0]["start"], ch[0]["end"]), (1, 8))

    def test_empty_raw_whole(self):                         # T002 空→整段一章
        ch = normalize_chapters([], 6)
        self.assertEqual(len(ch), 1)
        self.assertEqual((ch[0]["start"], ch[0]["end"]), (1, 6))

    def test_n_zero_empty(self):                            # T002 n<=0→[]
        self.assertEqual(normalize_chapters([{"start": 1}], 0), [])


class TestExpiredTempIds(unittest.TestCase):
    NOW = "2026-08-10T00:00:00Z"

    def _c(self, cid, temp, days_ago):
        # days_ago 天前的 last_activity（相對 NOW）
        from datetime import datetime, timedelta, timezone
        base = datetime(2026, 8, 10, tzinfo=timezone.utc) - timedelta(days=days_ago)
        return {"id": cid, "temporary": temp,
                "last_activity_at": base.strftime("%Y-%m-%dT%H:%M:%SZ")}

    def test_expired_selected(self):                        # T002 過期暫存選中
        convos = [self._c(1, 1, 8), self._c(2, 1, 3)]       # #1 過期(8天)、#2 未過期(3天)
        self.assertEqual(expired_temp_ids(convos, self.NOW, 7), [1])

    def test_permanent_never_selected(self):                # T002 永久不選（即使很舊）
        self.assertEqual(expired_temp_ids([self._c(1, 0, 99)], self.NOW, 7), [])

    def test_boundary_exactly_ttl_not_expired(self):        # T002 剛好 7 天→未過期（>才過期）
        self.assertEqual(expired_temp_ids([self._c(1, 1, 7)], self.NOW, 7), [])

    def test_just_over_ttl(self):                           # T002 剛過 7 天
        c = self._c(1, 1, 7);
        # 再往前 1 秒讓它 > 7 天
        from datetime import datetime, timedelta, timezone
        c["last_activity_at"] = (datetime(2026,8,10,tzinfo=timezone.utc)
                                 - timedelta(days=7, seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(expired_temp_ids([c], self.NOW, 7), [1])

    def test_missing_or_bad_time_conservative(self):        # T002 缺/壞時間→保守不選
        self.assertEqual(expired_temp_ids(
            [{"id": 1, "temporary": 1, "last_activity_at": ""},
             {"id": 2, "temporary": 1, "last_activity_at": "壞掉的時間"}], self.NOW, 7), [])


class TestCheapTitle(unittest.TestCase):
    def test_first_user_truncated(self):                    # T003
        t = cheap_title([{"role": "user", "content": "為什麼殘差要用加法而不是別的" * 3}])
        self.assertTrue(t.startswith("為什麼殘差"))
        self.assertLessEqual(len(t), 20)

    def test_empty(self):                                   # T003
        self.assertEqual(cheap_title([]), "（暫存對話）")

    def test_missing_content(self):                         # T003 不崩
        self.assertIsInstance(cheap_title([{"role": "user"}]), str)


if __name__ == "__main__":
    unittest.main()
