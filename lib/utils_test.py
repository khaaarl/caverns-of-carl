import functools
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if _ROOT not in sys.path:
    sys.path.append(_ROOT)

from lib.utils import expr_match_keywords, parse_keyword_expr


class CustomExprParseAssertions:
    def assertMatches(self, expr, keywords):
        return self._assertMatch(expr, keywords, True)

    def assertNotMatches(self, expr, keywords):
        return self._assertMatch(expr, keywords, False)

    def _assertMatch(self, expr, keywords, desired_result):
        m = expr_match_keywords(expr, keywords)
        if bool(m) == bool(desired_result):
            return
        err_msg = "should not match"
        if desired_result:
            err_msg = "does not match"
        raise AssertionError(
            f"Expression '{expr}' {err_msg} {keywords}. Parsed expression: {parse_keyword_expr(expr)}"
        )


class TestExprParse(unittest.TestCase, CustomExprParseAssertions):
    def test_empty(self):
        self.assertMatches("", ["Blah", "Undead"])
        self.assertMatches("", [])

    def test_simple(self):
        self.assertMatches("undead", ["Blah", "Undead"])
        self.assertNotMatches("undead", ["Blah", "Construct"])

    def test_two_words(self):
        self.assertNotMatches("flesh golem", ["Blah", "Undead"])
        self.assertMatches("flesh golem", ["Blah", "Flesh Golem"])

    def test_negation(self):
        expr = "not undead"
        self.assertNotMatches(expr, ["Blah", "Undead"])
        self.assertMatches(expr, ["Blah", "Flesh Golem"])

    def test_or(self):
        expr = "undead or flesh golem"
        self.assertMatches(expr, ["Blah", "Undead"])
        self.assertNotMatches(expr, ["Blah", "Construct"])
        self.assertMatches(expr, ["Blah", "Flesh Golem"])
        self.assertMatches(expr, ["Undead", "Flesh Golem"])

    def test_and(self):
        expr = "undead and urban"
        self.assertNotMatches(expr, ["Blah", "Undead"])
        self.assertNotMatches(expr, ["Blah", "Urban"])
        self.assertMatches(expr, ["Undead", "Urban"])

    def test_and_or_ordering1(self):
        expr = "thing1 or thing2 and thing3"
        self.assertMatches(expr, ["thing1"])
        self.assertMatches(expr, ["thing2", "thing3"])
        self.assertNotMatches(expr, ["thing2"])
        self.assertNotMatches(expr, ["thing3"])

    def test_and_or_ordering2(self):
        expr = "thing2 and thing3 or thing1"
        self.assertMatches(expr, ["thing1"])
        self.assertMatches(expr, ["thing2", "thing3"])
        self.assertNotMatches(expr, ["thing2"])
        self.assertNotMatches(expr, ["thing3"])

    def test_parens(self):
        expr = "(undead or construct) and urban"
        self.assertMatches(expr, ["undead", "urban"])
        self.assertMatches(expr, ["construct", "urban"])
        self.assertNotMatches(expr, ["construct"])
        self.assertNotMatches(expr, ["undead"])
        self.assertNotMatches(expr, ["urban"])

    def test_chain_and_not(self):
        # Specific test for a specific error
        expr = "goblinoid and not hobgoblinoid and not bugbearoid"
        self.assertMatches(expr, ["booyagh", "goblinoid"])
        self.assertNotMatches(expr, ["hobgoblinoid", "goblinoid"])
        self.assertNotMatches(expr, ["bugbearoid", "goblinoid"])

    def test_chain_and_not_parens(self):
        # Specific test for a specific error
        expr = "goblinoid and (not hobgoblinoid) and (not bugbearoid)"
        self.assertMatches(expr, ["booyagh", "goblinoid"])
        self.assertNotMatches(expr, ["hobgoblinoid", "goblinoid"])
        self.assertNotMatches(expr, ["bugbearoid", "goblinoid"])


if __name__ == "__main__":
    unittest.main()
