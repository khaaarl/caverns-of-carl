
import functools
import re
import random


def choice(seq, weights=None, cum_weights=None):
    if cum_weights is not None:
        return random.choices(seq, cum_weights=cum_weights, k=1)[0]
    if weights is not None:
        return random.choices(seq, weights=weights, k=1)[0]
    return random.choice(seq)


class WeightTreeNode:
    def __init__(self, left_weight, value=None, left=None, right=None):
        self.left_weight = left_weight
        self.value = value
        self.left, self.right = left, right

    def find_and_remove(self, weight):
        if self.left is None:
            prev_left_weight = self.left_weight
            self.left_weight = 0.0
            return (prev_left_weight, self.value)
        if weight < self.left_weight:
            dweight, value = self.left.find_and_remove(weight)
            self.left_weight -= dweight
            return (dweight, value)
        else:
            dweight, value = self.right.find_and_remove(weight - self.left_weight)
            return (dweight, value)

    @staticmethod
    def build(seq, weights, ix0, ix1):
        if ix1 - ix0 == 1:
            if weights is None:
                weight = 1.0
            else:
                weight = weights[ix0]
            return (WeightTreeNode(left_weight=weight, value=seq[ix0]), weight)
        ixr = ix0 + ((ix1 - ix0) >> 1)
        left, left_weight = WeightTreeNode.build(seq, weights, ix0, ixr)
        right, right_weight = WeightTreeNode.build(seq, weights, ixr, ix1)
        return (
            WeightTreeNode(left_weight=left_weight, left=left, right=right),
            left_weight + right_weight,
        )


def samples(seq, k=1, weights=None):
    if k <= 0:
        return []
    elif k == 1:
        yield choice(seq, weights=weights)
        return
    elif k > len(seq):
        raise ValueError(
            f"Number of samples k requested ({k}) larger than population"
        )
    tree, total_weight = WeightTreeNode.build(seq, weights, 0, len(seq))
    for _ in range(k):
        weight = random.random() * total_weight
        dweight, value = tree.find_and_remove(weight)
        total_weight -= dweight
        yield value


class Expr:
    pass


class NestedExpr(Expr):
    def __init__(self, exprs=None):
        self.exprs = exprs or []

    def __str__(self):
        return f"{type(self).__name__}{self.exprs}"

    def __repr__(self):
        return self.__str__()

    def __iter__(self):
        return self.exprs.__iter__()

    def mutate(self, func):
        for ix, item in enumerate(self.exprs):
            if isinstance(item, NestedExpr):
                item.mutate(func)
            else:
                self.exprs[ix] = func(item)


class ParenExpr(NestedExpr):
    @staticmethod
    def from_tokens(tokens):
        return ParenExpr._recursively_from_tokens(tokens, 0)[0]

    @staticmethod
    def _recursively_from_tokens(tokens, ix):
        output = []
        while ix < len(tokens):
            token = tokens[ix]
            ix += 1
            if token == ")":
                break
            elif token == "(":
                val, ix = ParenExpr._recursively_from_tokens(tokens, ix)
                output.append(val)
            else:
                output.append(token)
        return (ParenExpr(output), ix)


class OrExpr(NestedExpr):
    @staticmethod
    def from_tokens(tokens):
        or_groups = []
        cur = []
        for token in tokens:
            if token == "OR":
                if cur:
                    or_groups.append(cur)
                cur = []
            elif isinstance(token, ParenExpr):
                if "OR" in token.exprs:
                    cur.append(OrExpr.from_tokens(token))
                else:
                    cur.append(token)
            else:
                cur.append(token)
        if cur:
            or_groups.append(cur)
        return OrExpr(or_groups)


class AndExpr(NestedExpr):
    @staticmethod
    def from_tokens(tokens):
        if isinstance(tokens, str):
            return tokens
        and_groups = []
        cur = []
        for token in tokens:
            if token == "AND":
                and_groups.append(cur)
                cur = []
            elif isinstance(token, list):
                cur.append([AndExpr.from_tokens(x) for x in token])
            elif isinstance(token, ParenExpr):
                if "AND" in token.exprs:
                    cur.append(AndExpr.from_tokens(token))
                else:
                    cur.append(token)
            elif isinstance(token, OrExpr):
                o = [AndExpr.from_tokens(l) for l in token]
                cur.append(OrExpr(o))
            else:
                cur.append(token)
        and_groups.append(cur)
        return AndExpr(and_groups)


@functools.cache
def parse_keyword_expr(s):
    tokens = re.split("([()]| OR | AND )", s.upper())
    tokens = [x.strip() for x in tokens if x.strip()]
    expr = ParenExpr.from_tokens(tokens)
    expr = OrExpr.from_tokens(expr)
    expr = AndExpr.from_tokens([expr])
    return expr

def _expr_match_keywords(expr, keywords):
    if isinstance(expr, str):
        return expr in keywords
    elif isinstance(expr, AndExpr) or isinstance(expr, list):
        for item in expr:
            if not _expr_match_keywords(item, keywords):
                return False
        return True
    elif isinstance(expr, OrExpr):
        for item in expr:
            if _expr_match_keywords(item, keywords):
                return True
        return False
    else:
        raise ValueError(f"expr has weird type: {expr}")


def expr_match_keywords(expr, keywords):
    if not expr:
        return True
    keywords = {x.upper() for x in keywords}
    if isinstance(expr, str):
        expr = parse_keyword_expr(expr)
    return _expr_match_keywords(expr, keywords)