"""spec 039 真跑照出：knowfield.* 的子 logger 在正式執行時被靜默吞掉（憲章 V）。"""
import logging
import unittest

from knowfield.logging_setup import get_logger


class TestPackageLoggingReachesHandler(unittest.TestCase):
    def test_child_logger_of_untouched_module_is_handled(self):
        """⚠️ get_logger('knowfield.web') 只把 handler 掛在 knowfield.web 上，
        於是 knowfield.text.translate 這種**沒人呼叫過 get_logger** 的模組
        往上找不到任何 handler → 走 lastResort（WARNING）→ INFO 全丟。

        後果：translate.py 的「第 N 塊退回原文」在正式執行時**從來沒被印出來過**，
        而那正是診斷翻譯降級唯一的線索。"""
        for n in ("knowfield", "knowfield.web", "knowfield.text.translate"):
            lg = logging.getLogger(n)
            lg.handlers.clear()
        get_logger("knowfield.web")                       # 模擬 app.py 的呼叫
        child = logging.getLogger("knowfield.text.translate")
        self.assertTrue(child.isEnabledFor(logging.INFO), "子 logger 的 INFO 被關掉了")
        chain, cur = [], child
        while cur:
            chain.extend(cur.handlers)
            cur = cur.parent if cur.propagate else None
        self.assertTrue(chain, "整條鏈上沒有任何 handler → INFO 會被丟掉")
