import functools
import unittest

from utils import expr_match_keywords


class TestExprParse(unittest.TestCase):
    def test_empty(self):
        expr = ""
        m = functools.partial(expr_match_keywords, expr)
        self.assertTrue(m(["Blah", "Undead"]))
        self.assertTrue(m([]))

    def test_simple(self):
        expr = "undead"
        m = functools.partial(expr_match_keywords, expr)
        self.assertTrue(m(["Blah", "Undead"]))
        self.assertFalse(m(["Blah", "Construct"]))

    def test_or(self):
        expr = "undead or flesh golem"
        m = functools.partial(expr_match_keywords, expr)
        self.assertTrue(m(["Blah", "Undead"]))
        self.assertFalse(m(["Blah", "Construct"]))
        self.assertTrue(m(["Blah", "Flesh Golem"]))
        self.assertTrue(m(["Undead", "Flesh Golem"]))

    def test_and(self):
        expr = "undead and urban"
        m = functools.partial(expr_match_keywords, expr)
        self.assertFalse(m(["Blah", "Undead"]))
        self.assertFalse(m(["Blah", "Urban"]))
        self.assertTrue(m(["Undead", "Urban"]))

    def test_parens(self):
        expr = "(undead or construct) and urban"
        m = functools.partial(expr_match_keywords, expr)
        self.assertTrue(m(["undead", "urban"]))
        self.assertTrue(m(["construct", "urban"]))
        self.assertFalse(m(["construct"]))
        self.assertFalse(m(["undead"]))
        self.assertFalse(m(["urban"]))

    def test_and_or_ordering(self):
        expr = "thing1 or thing2 and thing3"
        m = functools.partial(expr_match_keywords, expr)
        self.assertTrue(m(["thing1"]))
        self.assertTrue(m(["thing2", "thing3"]))
        self.assertFalse(m(["thing2"]))
        self.assertFalse(m(["thing3"]))


if __name__ == "__main__":
    unittest.main()
