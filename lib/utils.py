import functools
import math
import os
import re
import random
import unicodedata

COC_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


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
            dweight, value = self.right.find_and_remove(
                weight - self.left_weight
            )
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


class BNFRule:
    def expression(self):
        "[rule, rule, rule, ...]"
        raise NotImplementedError()

    def parse(self, tokens):
        rules = self.expression()
        return self._parse_tokens_with_rules(tokens, rules)

    def _parse_tokens_with_rules(self, tokens, rules):
        if len(tokens) < len(rules):
            return None
        if len(rules) == 1:
            p = rules[0].parse(tokens)
            if p:
                return [p]
            else:
                return None
        for ix in range(1, len(tokens) - len(rules) + 2):
            p0 = rules[0].parse(tokens[:ix])
            if not p0:
                continue
            pn = self._parse_tokens_with_rules(tokens[ix:], rules[1:])
            if pn:
                return [p0] + pn
        return None

    def __repr__(self):
        return str(self.__class__)


class LiteralRule(BNFRule):
    def __init__(self, literal):
        self.literal = literal

    def parse(self, tokens):
        if len(tokens) == 1 and tokens[0] == self.literal:
            return self
        return None

    def __repr__(self):
        return f"L('{self.literal}')"


class EitherRule(BNFRule):
    def __init__(self, rule_options):
        self.rule_options = list(rule_options)

    def parse(self, tokens):
        for rule in self.rule_options:
            p = rule.parse(tokens)
            if p:
                return p
        return None

    def __repr__(self):
        return f"EitherRule({', '.join([repr(x) for x in self.rule_options])})"


class NonSpecialTokensRule(BNFRule):
    def __init__(self, tokens=None):
        self.keyword = None
        if tokens:
            self.keyword = " ".join(tokens)

    def parse(self, tokens):
        for token in tokens:
            if token in {"(", ")", "OR", "AND", "NOT"}:
                return None
        return NonSpecialTokensRule(tokens)

    def match(self, keywords):
        return self.keyword in keywords or not self.keyword

    def __repr__(self):
        return f"'{self.keyword}'"


class NotRule(BNFRule):
    def __init__(self, internal_rule=None):
        self.internal_rule = internal_rule

    def expression(self):
        return [LiteralRule("NOT"), KeywordExprRule()]

    def parse(self, tokens):
        p = super().parse(tokens)
        if not p:
            return None
        return NotRule(p[1])

    def match(self, keywords):
        return not self.internal_rule.match(keywords)

    def __repr__(self):
        return f"NotRule({self.internal_rule})"


class OrRule(BNFRule):
    def __init__(self, left=None, right=None):
        self.left, self.right = left, right

    def expression(self):
        return [KeywordExprRule(), LiteralRule("OR"), KeywordExprRule()]

    def parse(self, tokens):
        p = super().parse(tokens)
        if not p:
            return None
        return OrRule(p[0], p[2])

    def match(self, keywords):
        return self.left.match(keywords) or self.right.match(keywords)

    def __repr__(self):
        return f"OrRule({self.left}, {self.right})"


class AndRule(BNFRule):
    def __init__(self, left=None, right=None):
        self.left, self.right = left, right

    def expression(self):
        return [KeywordExprRule(), LiteralRule("AND"), KeywordExprRule()]

    def parse(self, tokens):
        p = super().parse(tokens)
        if not p:
            return None
        return AndRule(p[0], p[2])

    def match(self, keywords):
        return self.left.match(keywords) and self.right.match(keywords)

    def __repr__(self):
        return f"AndRule({self.left}, {self.right})"


class ParensRule(BNFRule):
    def expression(self):
        return [LiteralRule("("), KeywordExprRule(), LiteralRule(")")]

    def parse(self, tokens):
        p = super().parse(tokens)
        if not p:
            return None
        return p[1]


class KeywordExprRule(EitherRule):
    def __init__(self):
        super().__init__(
            [
                ParensRule(),
                OrRule(),
                AndRule(),
                NotRule(),
                NonSpecialTokensRule(),
            ]
        )

    def __repr__(self):
        return "KeywordExprRule"


@functools.cache
def parse_keyword_expr(s):
    tokens = re.split("([() ])", s.upper().strip())
    tokens = [x.strip() for x in tokens if x.strip()]
    return KeywordExprRule().parse(tokens)


def expr_match_keywords(expr, keywords):
    if not expr:
        return True
    keywords = {x.upper() for x in keywords}
    if isinstance(expr, str):
        if not expr.strip():  # Blank matches everything.
            return True
        expr = parse_keyword_expr(expr)
    return expr.match(keywords)


def eval_dice(e):
    e = str(e).strip().replace("-", "+-")
    l = [x.strip() for x in e.split("+") if x.strip()]
    total = 0
    for s in l:
        subtract = False
        if s.startswith("-"):
            s = s[1:].strip()
            subtract = True
        tmp = 0
        m = re.match("^([0-9]*)[dD]([0-9]+)$", s)
        if m:
            for _ in range(int(m.group(1) or "1")):
                tmp += random.randrange(1, int(m.group(2)) + 1)
        else:
            tmp += int(s)
        if subtract:
            total -= tmp
        else:
            total += tmp
    return total


def bfs(d, start, max_depth=None):
    if max_depth is not None and max_depth < 0:
        return []
    output = [set([start])]
    seen = set([start])
    while True:
        if max_depth is not None and len(output) > max_depth:
            break
        next_layer = set()
        for item in output[-1]:
            for neighbor in d[item]:
                if neighbor in seen:
                    continue
                next_layer.add(neighbor)
                seen.add(neighbor)
        if not next_layer:
            break
        output.append(next_layer)
    return output


def dfs(
    d,
    start,
    seen=None,
    accum=None,
    prev=None,
    include_previous=False,
    randomize=False,
):
    accum = accum or []
    seen = seen or set()
    seen.add(start)
    if include_previous:
        accum.append((prev, start))
    else:
        accum.append(start)
    next_layer = d[start]
    if randomize:
        next_layer = list(next_layer)
        random.shuffle(next_layer)
    for other in next_layer:
        if other not in seen:
            dfs(d, other, seen, accum, start, include_previous, randomize)
    return accum


def neighbor_coords(x, y, cardinal=True, diagonal=False):
    l = []
    if cardinal:
        l += [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if diagonal:
        l += [(-1, -1), (1, -1), (-1, 1), (1, 1)]
    for dx, dy in l:
        yield (x + dx, y + dy)


@functools.total_ordering
class CharStyle:
    def __init__(self, r, g, b, *, is_bold=False, is_underline=False):
        self.r = r
        self.g = g
        self.b = b
        self.is_bold = is_bold
        self.is_underline = is_underline

    def color_hex(self):
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"

    def __str__(self):
        s = self.color_hex()
        if self.is_bold:
            s += " bold"
        if self.is_underline:
            s += " underline"
        return s

    @staticmethod
    def from_ansi(possible_code):
        m = re.match(r"^\[[0-9];[0-9][0-9]m$", possible_code)
        if not m:
            return None
        style_code = int(possible_code[1])
        color_code = int(possible_code[3:5])
        color_hex = {
            30: "#000",
            31: "#b00",
            32: "#0b0",
            33: "#bb0",
            34: "#00c",
            35: "#b0c",
            36: "#0bc",
            37: "#bbc",
            90: "#000",
            91: "#f00",
            92: "#0f0",
            93: "#ff0",
            94: "#00f",
            95: "#f0f",
            96: "#0ff",
            97: "#fff",
        }[color_code]
        return CharStyle(
            r=int(round(int(color_hex[1], 16) * 255 / 15.0)),
            g=int(round(int(color_hex[2], 16) * 255 / 15.0)),
            b=int(round(int(color_hex[3], 16) * 255 / 15.0)),
            is_bold=style_code == 1,
            is_underline=style_code == 4,
        )

    def tuple(self):
        return (self.r, self.g, self.b, self.is_bold, self.is_underline)

    def __lt__(self, other):
        return self.tuple() < other.tuple()

    def __eq__(self, other):
        if other is None:
            return False
        return self.tuple() == other.tuple()

    def __hash__(self):
        return self.tuple().__hash__()


class StyledChar:
    def __init__(self, c, style=None):
        if isinstance(c, StyledChar):
            self.c = c.c
            self.style = c.style
            self.bookmark_name = c.bookmark_name
            self.link_destination = c.link_destination
            return
        self.c = c
        self.style = style
        self.bookmark_name = None
        self.link_destination = None

    def __str__(self):
        if not self.style:
            return self.c
        return "{" + self.c + " " + str(self.style) + "}"


class StyledString:
    def __init__(self, chars=None):
        if isinstance(chars, StyledString):
            self.chars = list(chars.chars)
            return
        if isinstance(chars, str):
            self.chars = StyledString._list_from_ascii(chars)
            return
        if isinstance(chars, StyledChar):
            self.chars = [chars]
            return
        self.chars = [StyledChar(x) for x in chars or []]

    def unstyled(self):
        l = []
        for c in self.chars:
            l.append(c.c)
        return "".join(l)

    def __str__(self):
        return "".join([str(x) for x in self.chars])

    def split_by_style(self):
        output = []
        accum = []
        cur_style = None
        for c in self.chars:
            if c.style != cur_style:
                if accum:
                    output.append(StyledString(accum))
                    accum = []
                cur_style = c.style
            accum.append(c)
        if accum:
            output.append(StyledString(accum))
        return output

    def join(self, seq):
        seq = list(seq)
        accum = []
        for ix, item in enumerate(seq):
            for c in StyledString(item).chars:
                accum.append(c)
            if ix + 1 < len(seq):
                for c in self.chars:
                    accum.append(c)
        return StyledString(accum)

    def split(self, separator):
        # TODO: handle separators that aren't just len 1 strings
        output = []
        tmp = []
        for c in self.chars:
            if c.c == separator:
                output.append(StyledString("").join(tmp))
                tmp = []
                continue
            tmp.append(c)
        if tmp:
            output.append(StyledString("").join(tmp))
        return output

    @staticmethod
    def _list_from_ascii(text):
        output = []
        ix = 0
        while ix < len(text):
            style = CharStyle.from_ansi(text[ix : ix + 6])
            if style:
                output.append(StyledChar(text[ix + 6], style))
                ix += 7
            else:
                output.append(StyledChar(text[ix]))
                ix += 1
        return output


class DocLink:
    def __init__(self, *args, content=None, destination=None):
        if len(args) == 2:
            content = args[0]
            destination = args[1]
        elif len(args) == 1:
            content = args[0]
            destination = args[0]
        self.content = content
        self.destination = destination


class DocBookmark:
    def __init__(self, name, content=None):
        self.name = name
        self.content = content or name


class Doc:
    def __init__(self, *args, header=None, body=None, separator="\n"):
        if len(args) == 2:
            header = args[0]
            body = args[1]
        elif len(args) == 1:
            body = args[0]
        self.header = header
        self.body = body
        self.separator = separator

    def __str__(self):
        return self.flat_str()

    def flat_str(self, *, separator=None):
        if separator is None:
            separator = self.separator
        o = []
        if self.header is not None:
            o.append(self.flat_header(separator=separator))
        if self.body is not None:
            o.append(self.flat_body(separator=separator))
        return StyledString(separator).join(o)

    def flat_header(self, *, separator=None):
        if separator is None:
            separator = self.separator
        return self._flat_thing(self.header, separator=separator)

    def flat_body(self, *, separator=None):
        if separator is None:
            separator = self.separator
        return self._flat_thing(self.body, separator=separator)

    def _flat_thing(self, thing, *, separator="\n"):
        if isinstance(thing, str):
            return StyledString(thing)
        if isinstance(thing, StyledString):
            return thing
        if isinstance(thing, Doc):
            return thing.flat_str()
        if isinstance(thing, DocLink):
            tmp = self._flat_thing(thing.content)
            if thing.destination:
                for c in tmp.chars:
                    c.link_destination = thing.destination
            return tmp
        if isinstance(thing, DocBookmark):
            tmp = self._flat_thing(thing.content)
            if thing.name:
                for c in tmp.chars:
                    c.bookmark_name = thing.name
            return tmp
        o = []
        if isinstance(thing, list):
            for x in thing:
                o.append(self._flat_thing(x))
        return StyledString(separator).join(o)


def random_dc(level):
    lo = int(math.floor(level * 0.7 + 8))
    hi = int(math.ceil(level * 0.8 + 12))
    return random.randrange(lo, hi + 1)


def remove_non_ascii(text):
    # Normalize the Unicode string to decompose accented characters
    normalized = unicodedata.normalize("NFKD", text)
    # Encode to ASCII bytes, ignoring errors, then decode back to a string
    return normalized.encode("ascii", "ignore").decode("ascii")
