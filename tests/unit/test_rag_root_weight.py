"""T010 [US3]：RagService._weight root > explainer > 1.0（重吸引子）。"""

import unittest

from learnnews.rag.service import RagService


class TestRootWeight(unittest.TestCase):
    def test_weight_tiers(self):
        svc = RagService(repo=None, embedder=None, answerer=None,
                         explainer_weight=1.5, root_weight=2.0)
        self.assertEqual(svc._weight("root"), 2.0)
        self.assertEqual(svc._weight("explainer"), 1.5)
        self.assertEqual(svc._weight("ordinary"), 1.0)
        self.assertGreater(svc._weight("root"), svc._weight("explainer"))
        self.assertGreater(svc._weight("explainer"), svc._weight("ordinary"))


if __name__ == "__main__":
    unittest.main()
