from __future__ import annotations

import builtins
import functools
import math
import os
import random
import re
import unicodedata
from typing import Any

COC_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def choice(
    seq: Any,
    weights: list[float] | None = None,
    cum_weights: list[float] | None = None,
) -> Any:
    """Pick a single random element from seq, with optional weighting."""
    if cum_weights is not None:
        return random.choices(seq, cum_weights=cum_weights, k=1)[0]
    if weights is not None:
        return random.choices(seq, weights=weights, k=1)[0]
    return random.choice(seq)


class WeightTreeNode:
    """Binary tree for weighted sampling without replacement.

    Used by samples() to efficiently draw multiple unique elements from
    a weighted sequence. Each draw removes the chosen element's weight
    from the tree, preventing it from being selected again.
    """

    def __init__(
        self,
        left_weight: float,
        value: Any = None,
        left: WeightTreeNode | None = None,
        right: WeightTreeNode | None = None,
    ) -> None:
        self.left_weight: float = left_weight
        self.value: Any = value
        self.left: WeightTreeNode | None = left
        self.right: WeightTreeNode | None = right

    def find_and_remove(self, weight: float) -> tuple[float, Any]:
        if self.left is None:
            prev_left_weight = self.left_weight
            self.left_weight = 0.0
            return (prev_left_weight, self.value)
        if weight < self.left_weight:
            dweight, value = self.left.find_and_remove(weight)
            self.left_weight -= dweight
            return (dweight, value)
        else:
            assert self.right is not None
            dweight, value = self.right.find_and_remove(
                weight - self.left_weight
            )
            return (dweight, value)

    @staticmethod
    def build(
        seq: Any, weights: list[float] | None, ix0: int, ix1: int
    ) -> tuple[WeightTreeNode, float]:
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


def samples(seq: Any, k: int = 1, weights: list[float] | None = None) -> Any:
    """Yield k unique elements from seq via weighted sampling without replacement."""
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
    def expression(self) -> list[BNFRule]:
        "[rule, rule, rule, ...]"
        raise NotImplementedError()

    def match(self, keywords: set[str]) -> bool:
        raise NotImplementedError()

    def parse(self, tokens: list[str]) -> Any:
        rules = self.expression()
        return self._parse_tokens_with_rules(tokens, rules)

    def _parse_tokens_with_rules(
        self, tokens: list[str], rules: list[BNFRule]
    ) -> list[Any] | None:
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

    def __repr__(self) -> str:
        return str(self.__class__)


class LiteralRule(BNFRule):
    def __init__(self, literal: str) -> None:
        self.literal: str = literal

    def parse(self, tokens: list[str]) -> LiteralRule | None:
        if len(tokens) == 1 and tokens[0] == self.literal:
            return self
        return None

    def __repr__(self) -> str:
        return f"L('{self.literal}')"


class EitherRule(BNFRule):
    def __init__(self, rule_options: Any) -> None:
        self.rule_options: list[BNFRule] = list(rule_options)

    def parse(self, tokens: list[str]) -> Any:
        for rule in self.rule_options:
            p = rule.parse(tokens)
            if p:
                return p
        return None

    def __repr__(self) -> str:
        return f"EitherRule({', '.join([repr(x) for x in self.rule_options])})"


class NonSpecialTokensRule(BNFRule):
    def __init__(self, tokens: list[str] | None = None) -> None:
        self.keyword: str | None = None
        if tokens:
            self.keyword = " ".join(tokens)

    def parse(self, tokens: list[str]) -> NonSpecialTokensRule | None:
        for token in tokens:
            if token in {"(", ")", "OR", "AND", "NOT"}:
                return None
        return NonSpecialTokensRule(tokens)

    def match(self, keywords: set[str]) -> bool:
        return self.keyword in keywords or not self.keyword

    def __repr__(self) -> str:
        return f"'{self.keyword}'"


class NotRule(BNFRule):
    def __init__(self, internal_rule: BNFRule | None = None) -> None:
        self.internal_rule: BNFRule | None = internal_rule

    def expression(self) -> list[BNFRule]:
        return [LiteralRule("NOT"), KeywordExprRule()]

    def parse(self, tokens: list[str]) -> NotRule | None:
        p = super().parse(tokens)
        if not p:
            return None
        return NotRule(p[1])

    def match(self, keywords: set[str]) -> bool:
        assert self.internal_rule is not None
        return not self.internal_rule.match(keywords)

    def __repr__(self) -> str:
        return f"NotRule({self.internal_rule})"


class OrRule(BNFRule):
    def __init__(
        self, left: BNFRule | None = None, right: BNFRule | None = None
    ) -> None:
        self.left: BNFRule | None = left
        self.right: BNFRule | None = right

    def expression(self) -> list[BNFRule]:
        return [KeywordExprRule(), LiteralRule("OR"), KeywordExprRule()]

    def parse(self, tokens: list[str]) -> OrRule | None:
        p = super().parse(tokens)
        if not p:
            return None
        return OrRule(p[0], p[2])

    def match(self, keywords: set[str]) -> bool:
        assert self.left is not None and self.right is not None
        return self.left.match(keywords) or self.right.match(keywords)

    def __repr__(self) -> str:
        return f"OrRule({self.left}, {self.right})"


class AndRule(BNFRule):
    def __init__(
        self, left: BNFRule | None = None, right: BNFRule | None = None
    ) -> None:
        self.left: BNFRule | None = left
        self.right: BNFRule | None = right

    def expression(self) -> list[BNFRule]:
        return [KeywordExprRule(), LiteralRule("AND"), KeywordExprRule()]

    def parse(self, tokens: list[str]) -> AndRule | None:
        p = super().parse(tokens)
        if not p:
            return None
        return AndRule(p[0], p[2])

    def match(self, keywords: set[str]) -> bool:
        assert self.left is not None and self.right is not None
        return self.left.match(keywords) and self.right.match(keywords)

    def __repr__(self) -> str:
        return f"AndRule({self.left}, {self.right})"


class ParensRule(BNFRule):
    def expression(self) -> list[BNFRule]:
        return [LiteralRule("("), KeywordExprRule(), LiteralRule(")")]

    def parse(self, tokens: list[str]) -> Any:
        p = super().parse(tokens)
        if not p:
            return None
        return p[1]


class KeywordExprRule(EitherRule):
    def __init__(self) -> None:
        super().__init__(
            [
                ParensRule(),
                OrRule(),
                AndRule(),
                NotRule(),
                NonSpecialTokensRule(),
            ]
        )

    def __repr__(self) -> str:
        return "KeywordExprRule"


@functools.cache
def parse_keyword_expr(s: str) -> Any:
    """Parse a keyword filter expression into a matchable rule tree.

    Supports AND, OR, NOT, and parentheses. Example:
    parse_keyword_expr("undead OR (beast AND NOT flying)")
    """
    tokens = re.split("([() ])", s.upper().strip())
    tokens = [x.strip() for x in tokens if x.strip()]
    return KeywordExprRule().parse(tokens)


def expr_match_keywords(expr: Any, keywords: list[str] | set[str]) -> bool:
    """Test whether a set of keywords matches a filter expression.

    expr can be a parsed rule tree or a string (which will be parsed).
    A falsy/blank expression matches everything.
    """
    if not expr:
        return True
    keywords = {x.upper() for x in keywords}
    if isinstance(expr, str):
        if not expr.strip():  # Blank matches everything.
            return True
        expr = parse_keyword_expr(expr)
    return expr.match(keywords)


def eval_dice(e: int | float | str) -> int:
    """Evaluate a D&D dice notation string and return the rolled total.

    Supports standard notation: "2d6+3", "d20", "4d8-2", "10".
    Numeric inputs are returned as-is (converted to int).
    """
    e = str(e).strip().replace("-", "+-")
    terms = [x.strip() for x in e.split("+") if x.strip()]
    total = 0
    for s in terms:
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


def bfs(
    d: dict[Any, Any],
    start: Any,
    max_depth: int | None = None,
) -> list[set[Any]]:
    """Breadth-first search on an adjacency dict.

    Returns a list of sets, one per depth level: [depth_0, depth_1, ...].
    d maps each node to its neighbors.
    """
    if max_depth is not None and max_depth < 0:
        return []
    output: list[set[Any]] = [set([start])]
    seen: set[Any] = set([start])
    while True:
        if max_depth is not None and len(output) > max_depth:
            break
        next_layer: set[Any] = set()
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
    d: dict[Any, Any],
    start: Any,
    seen: set[Any] | None = None,
    accum: list[Any] | None = None,
    prev: Any = None,
    include_previous: bool = False,
    randomize: bool = False,
) -> list[Any]:
    """Depth-first search on an adjacency dict.

    Returns nodes in visit order. If include_previous is True, returns
    (parent, node) tuples instead. If randomize is True, shuffles
    neighbor order at each step.
    """
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


def astar_corridor_path(
    tiles: Any,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    max_steps: int = 200,
    turn_penalty: int = 2,
) -> list[tuple[int, int]] | None:
    """Find a cardinal-movement path from (x1,y1) to (x2,y2) through WallTile only.

    Returns a list of (x, y) coordinates, or None if no path exists.
    Uses A* with Manhattan distance heuristic and a turn penalty to
    prefer straighter paths.
    """
    import heapq

    from lib.tile import WallTile

    width = len(tiles)
    height = len(tiles[0])

    def heuristic(x: int, y: int) -> int:
        return abs(x - x2) + abs(y - y2)

    # (f_score, g_score, x, y, prev_dx, prev_dy)
    start_entry = (heuristic(x1, y1), 0, x1, y1, 0, 0)
    open_set: list[tuple[int, int, int, int, int, int]] = [start_entry]
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_scores: dict[tuple[int, int], int] = {(x1, y1): 0}

    while open_set:
        _, g, x, y, pdx, pdy = heapq.heappop(open_set)
        if x == x2 and y == y2:
            # Reconstruct path
            path = [(x, y)]
            while (x, y) in came_from:
                x, y = came_from[(x, y)]
                path.append((x, y))
            path.reverse()
            return path
        if g > max_steps:
            continue
        if g > g_scores.get((x, y), max_steps + 1):
            continue
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if nx < 0 or nx >= width or ny < 0 or ny >= height:
                continue
            # Allow walking through walls and the destination (which may
            # be a room floor tile)
            tile = tiles[nx][ny]
            is_dest = nx == x2 and ny == y2
            if not isinstance(tile, WallTile) and not is_dest:
                continue
            cost = 1
            if pdx != 0 or pdy != 0:
                if dx != pdx or dy != pdy:
                    cost += turn_penalty
            new_g = g + cost
            if new_g < g_scores.get((nx, ny), max_steps + 1):
                g_scores[(nx, ny)] = new_g
                f = new_g + heuristic(nx, ny)
                heapq.heappush(open_set, (f, new_g, nx, ny, dx, dy))
                came_from[(nx, ny)] = (x, y)
    return None


def _path_to_waypoints(path: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Convert a raw A* path into a list of waypoints at direction changes."""
    if len(path) <= 2:
        return path
    waypoints = [path[0]]
    for i in range(1, len(path) - 1):
        px, py = path[i - 1]
        x, y = path[i]
        nx, ny = path[i + 1]
        dx1, dy1 = x - px, y - py
        dx2, dy2 = nx - x, ny - y
        if dx1 != dx2 or dy1 != dy2:
            waypoints.append((x, y))
    waypoints.append(path[-1])
    return waypoints


def neighbor_coords(
    x: int, y: int, cardinal: bool = True, diagonal: bool = False
) -> Any:
    """Yield (x, y) coordinates of neighboring grid positions."""
    offsets: list[tuple[int, int]] = []
    if cardinal:
        offsets += [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if diagonal:
        offsets += [(-1, -1), (1, -1), (-1, 1), (1, 1)]
    for dx, dy in offsets:
        yield (x + dx, y + dy)


@functools.total_ordering
class CharStyle:
    """RGB color and formatting (bold/underline) for a single character.

    Supports ordering, hashing, and conversion to hex color strings.
    Can be parsed from ANSI escape codes via CharStyle.from_ansi().
    """

    def __init__(
        self,
        r: int,
        g: int,
        b: int,
        *,
        is_bold: bool = False,
        is_underline: bool = False,
    ) -> None:
        self.r: int = r
        self.g: int = g
        self.b: int = b
        self.is_bold: bool = is_bold
        self.is_underline: bool = is_underline

    def color_hex(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"

    def __str__(self) -> str:
        s = self.color_hex()
        if self.is_bold:
            s += " bold"
        if self.is_underline:
            s += " underline"
        return s

    @staticmethod
    def from_ansi(possible_code: str) -> CharStyle | None:
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

    def tuple(self) -> builtins.tuple[int, int, int, bool, bool]:
        return (self.r, self.g, self.b, self.is_bold, self.is_underline)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, CharStyle):
            return NotImplemented
        return self.tuple() < other.tuple()

    def __eq__(self, other: object) -> bool:
        if other is None:
            return False
        if not isinstance(other, CharStyle):
            return NotImplemented
        return self.tuple() == other.tuple()

    def __hash__(self) -> int:
        return self.tuple().__hash__()


class StyledChar:
    def __init__(
        self, c: str | StyledChar, style: CharStyle | None = None
    ) -> None:
        if isinstance(c, StyledChar):
            self.c: str = c.c
            self.style: CharStyle | None = c.style
            self.bookmark_name: str | None = c.bookmark_name
            self.link_destination: str | None = c.link_destination
            return
        self.c = c
        self.style = style
        self.bookmark_name = None
        self.link_destination = None

    def __str__(self) -> str:
        if not self.style:
            return self.c
        return "{" + self.c + " " + str(self.style) + "}"


class StyledString:
    """A string with per-character styling (color, bold, underline).

    Can be constructed from a plain str (with optional embedded ANSI codes),
    another StyledString, a StyledChar, or a list of StyledChars. Supports
    split, join, and unstyled() for plain text output.
    """

    def __init__(
        self, chars: StyledString | str | StyledChar | list[Any] | None = None
    ) -> None:
        if isinstance(chars, StyledString):
            self.chars: list[StyledChar] = list(chars.chars)
            return
        if isinstance(chars, str):
            self.chars = StyledString._list_from_ascii(chars)
            return
        if isinstance(chars, StyledChar):
            self.chars = [chars]
            return
        self.chars = [StyledChar(x) for x in chars or []]

    def unstyled(self) -> str:
        char_strings: list[str] = []
        for c in self.chars:
            char_strings.append(c.c)
        return "".join(char_strings)

    def __str__(self) -> str:
        return "".join([str(x) for x in self.chars])

    def split_by_style(self) -> list[StyledString]:
        output: list[StyledString] = []
        accum: list[StyledChar] = []
        cur_style: CharStyle | None = None
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

    def join(self, seq: Any) -> StyledString:
        seq = list(seq)
        accum: list[StyledChar] = []
        for ix, item in enumerate(seq):
            for c in StyledString(item).chars:
                accum.append(c)
            if ix + 1 < len(seq):
                for c in self.chars:
                    accum.append(c)
        return StyledString(accum)

    def split(self, separator: str) -> list[StyledString]:
        # TODO: handle separators that aren't just len 1 strings
        output: list[StyledString] = []
        tmp: list[Any] = []
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
    def _list_from_ascii(text: str) -> list[StyledChar]:
        output: list[StyledChar] = []
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
    def __init__(
        self,
        *args: str,
        content: str | None = None,
        destination: str | None = None,
    ) -> None:
        if len(args) == 2:
            content = args[0]
            destination = args[1]
        elif len(args) == 1:
            content = args[0]
            destination = args[0]
        self.content: str | None = content
        self.destination: str | None = destination


class DocBookmark:
    def __init__(self, name: str, content: str | None = None) -> None:
        self.name: str = name
        self.content: str = content or name


class Doc:
    """A structured document with optional header and body.

    Content can be strings, StyledStrings, DocLinks, DocBookmarks,
    nested Docs, or lists thereof. Use flat_str() to render to a
    StyledString, or str() for plain text.
    """

    def __init__(
        self,
        *args: Any,
        header: Any = None,
        body: Any = None,
        separator: str = "\n",
    ) -> None:
        if len(args) == 2:
            header = args[0]
            body = args[1]
        elif len(args) == 1:
            body = args[0]
        self.header: Any = header
        self.body: Any = body
        self.separator: str = separator

    def __str__(self) -> str:
        return self.flat_str().unstyled()

    def flat_str(self, *, separator: str | None = None) -> StyledString:
        if separator is None:
            separator = self.separator
        o: list[Any] = []
        if self.header is not None:
            o.append(self.flat_header(separator=separator))
        if self.body is not None:
            o.append(self.flat_body(separator=separator))
        return StyledString(separator).join(o)

    def flat_header(self, *, separator: str | None = None) -> StyledString:
        if separator is None:
            separator = self.separator
        return self._flat_thing(self.header, separator=separator)

    def flat_body(self, *, separator: str | None = None) -> StyledString:
        if separator is None:
            separator = self.separator
        return self._flat_thing(self.body, separator=separator)

    def _flat_thing(
        self, thing: Any, *, separator: str = "\n"
    ) -> StyledString:
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
        o: list[Any] = []
        if isinstance(thing, list):
            for x in thing:
                o.append(self._flat_thing(x))
        return StyledString(separator).join(o)


def random_dc(level: int) -> int:
    """Generate a random D&D difficulty class (DC) appropriate for a given level."""
    lo = int(math.floor(level * 0.7 + 8))
    hi = int(math.ceil(level * 0.8 + 12))
    return random.randrange(lo, hi + 1)


def remove_non_ascii(text: str) -> str:
    # Normalize the Unicode string to decompose accented characters
    normalized = unicodedata.normalize("NFKD", text)
    # Encode to ASCII bytes, ignoring errors, then decode back to a string
    return normalized.encode("ascii", "ignore").decode("ascii")
