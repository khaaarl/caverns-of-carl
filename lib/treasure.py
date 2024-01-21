import functools
import json
import math
import os
import random
import re

import lib.tts as tts
from lib.utils import COC_ROOT_DIR, eval_dice


@functools.cache
def get_treasure_library(name):
    tl = TreasureLibrary(name=name)
    tl.load()
    return tl


@functools.cache
def book_library():
    filename = os.path.join(
        COC_ROOT_DIR, "reference_info", "misc", "books.json"
    )
    books = {}
    with open(filename) as f:
        blob = json.load(f)
        for book_obj in blob["books"]:
            book = Book(book_obj)
            if not book.title:
                continue
            books[book.title] = book
    return books


@functools.cache
def book_title_list():
    return sorted(book_library().keys())


@functools.cache
def book_list():
    return [book_library()[k] for k in sorted(book_library().keys())]


class Book:
    def __init__(self, obj):
        self.title = obj.get("Title")
        self.author = obj.get("Author")
        self.description = obj.get("Description")
        self.synopsis = obj.get("Synopsis")
        self.excerpt = obj.get("Excerpt")
        self.author_background = obj.get("AuthorBackground")
        self.keywords = set(obj.get("Keywords") or [])

    def tts_nickname(self):
        s = f"[u]{self.title}[/u]"
        if self.author:
            s += f" by {self.author}"
        return s

    def tts_description(self):
        o = []
        if self.description:
            o.append(self.description)
        if self.synopsis:
            o.append(self.synopsis)
        if self.excerpt:
            o.append("[i]" + self.excerpt + "[/i]")
        if self.author_background:
            o.append(self.author_background)
        return "\n\n".join(o)

    def tts_reference_nickname(self):
        if "Humor" in self.keywords:
            skin = "Comedy"
        else:
            skin = chr(random.randrange(ord("A"), ord("K")))
        return "Reference Book " + skin

    def tts_object(self):
        item = tts.reference_object(self.tts_reference_nickname())
        item["Nickname"] = self.tts_nickname()
        item["Description"] = self.tts_description()
        return item


class TreasureLibrary:
    def __init__(self, name):
        self.name = name
        self.tables = []
        self.items = []
        self.variants = []
        self.art_objects = {}
        self.gemstones = {}

    def load(self):
        filename = os.path.join(
            COC_ROOT_DIR, "reference_info", "treasure", f"{self.name}.json"
        )
        with open(filename) as f:
            blob = json.load(f)
            self.tables = blob["tables"]
            self.items = blob["items"]
            self.variants = blob["variants"]
            for d in blob["art objects"]:
                self.art_objects[int(d["gold"])] = d["names"]
            for d in blob["gemstones"]:
                self.gemstones[int(d["gold"])] = d["names"]

    def to_blob(self):
        return self

    def save(self):
        filename = os.path.join(
            COC_ROOT_DIR, "reference_info", "treasure", f"{self.name}.json"
        )
        with open(filename, "w") as f:
            json.dump(self.to_blob(), f, indent=2)

    def gen_horde(self, level, num_player_characters):
        table_use = [
            ("A", 80),
            ("B", min(20 + level * 5, 50)),
            ("C", min(25 + level * 3, 70)),
            ("D", min((level - 4) * 8, 108)),
            ("E", min((level - 10) * 10, 77)),
            ("F", 30),
            ("G", min(level * 2, 10)),
            ("H", min((level - 4) * 4, 25)),
            ("I", min((level - 10) * 5, 50)),
        ]
        contents = []
        contents_seen = set()
        for c, p in table_use:
            tmp = []
            for _ in range(2 * num_player_characters):
                if random.randrange(1000) < p:
                    item = self.roll_on_table(f"Magic Item Table {c}")
                    if item not in contents_seen:
                        contents_seen.add(item)
                        tmp.append(item)
            tmp.sort()
            contents = contents + tmp
        for _ in range(random.randrange(1, 5)):
            if random.random() < 0.25:
                contents.append(
                    "Adventuring Gear: "
                    + self.roll_on_table(f"PHB Adventuring Gear")
                )
        if random.random() < 0.1:
            contents.append("Trinket: " + self.roll_on_table(f"PHB Trinkets"))
        if random.random() < 0.1:
            contents.append("Trinket: " + self.roll_on_table(f"EE Trinkets"))
        if random.random() < 0.7:
            contents += self.gold_to_treasure(
                self._hoard_gp_quantity(level, num_player_characters)
                * random.random()
                * random.random()
            )
        contents = [x for x in contents if x]
        return contents

    def gold_to_treasure(self, gp):
        l = []
        treasure_type, d = random.choice(
            [("Gemstone", self.gemstones), ("Art Object", self.art_objects)]
        )
        lowest_key = None
        highest_key = None
        for k in d:
            if lowest_key is None or k < lowest_key:
                lowest_key = k
            if highest_key is None or k > highest_key:
                highest_key = k
        k_lo = lowest_key
        k_hi = highest_key
        for k in d:
            if k <= gp and abs(k - gp) <= abs(k_lo - gp):
                k_lo = k
            if k >= gp and abs(k - gp) <= abs(k_hi - gp):
                k_hi = k
        print(lowest_key, highest_key, k_lo, k_hi, gp)
        if gp < k_lo:
            if random.random() < (gp / k_lo):
                l.append(k_lo)
        elif gp > k_hi:
            n = int(math.floor(gp / k_hi))
            if random.random() < (gp % k_hi) / k_hi:
                n += 1
            for _ in range(n):
                l.append(k_hi)
        elif gp == k_lo:
            l.append(k_lo)
        elif gp == k_hi:
            l.append(k_hi)
        else:
            if random.random() < (k_hi - k_lo) / (gp - k_lo):
                l.append(k_hi)
            else:
                l.append(k_lo)
        print(l)
        l = [f"{treasure_type} ({k} gp): {random.choice(d[k])}" for k in l]
        return sorted(l)

    def _hoard_gp_quantity(
        self, level, num_player_characters, level_plus_minus=3.0
    ):
        level += level_plus_minus * (random.random() * 2.0 - 1)
        # loosely based on hoard numbers?
        return 2 ** (level / 2.5) * 15.0 * num_player_characters

    def gen_bookshelf_horde(self, level, num_player_characters):
        clvl = (level + 1) / 2
        freq = 50
        table_use = [
            "Spell scroll (cantrip): {spell-lvl0}",
            "Spell scroll (1st level): {spell-lvl1}",
            "Spell scroll (2nd level): {spell-lvl2}",
            "Spell scroll (3rd level): {spell-lvl3}",
            "Spell scroll (4th level): {spell-lvl4}",
            "Spell scroll (5th level): {spell-lvl5}",
            "Spell scroll (6th level): {spell-lvl6}",
            "Spell scroll (7th level): {spell-lvl7}",
            "Spell scroll (8th level): {spell-lvl8}",
            "Spell scroll (9th level): {spell-lvl9}",
        ]
        for lvl in range(10):
            p = freq * min(1.0 + (clvl - lvl) / 2.0, 1.0)
            table_use[lvl] = (table_use[lvl], p)
        contents = []
        contents_seen = set()
        for c, p in table_use:
            tmp = []
            for _ in range(2 * num_player_characters):
                if random.randrange(1000) < p:
                    item = self.expand_item(c)
                    if item not in contents_seen:
                        contents_seen.add(item)
                        tmp.append(item)
            tmp.sort()
            contents = contents + tmp
        contents = [x for x in contents if x]
        max_size = eval_dice("2d4")
        contents = contents[-max_size:]
        for _ in range(eval_dice("1d4-1")):
            title = random.choice(book_title_list())
            line = f"Book: {title}"
            if line not in contents_seen:
                contents.append(line)
                contents_seen.add(line)
        return contents

    def roll_on_table(self, table_name, d=100):
        table = None
        for t in self.tables:
            if t["name"].upper() == table_name.upper():
                table = t
        if table is None:
            raise KeyError()
        roll = random.randrange(d)
        item = None
        for d_range, value in table["table"]:
            lo, hi = None, None
            if "-" in d_range:
                lo, hi = map(int, d_range.split("-"))
            else:
                lo, hi = int(d_range), int(d_range)
            if roll >= lo and roll <= hi:
                item = value
        return self.expand_item(item or "")

    def expand_item(self, item):
        for i in self.items:
            if i["name"].upper() != item.upper():
                continue
            if i.get("variants"):
                item = random.choice(i["variants"])
        return self.expand_variant(item)

    def expand_variant(self, item):
        o = []
        for bit in re.split("({[^}]+})", item):
            if bit.startswith("{") and bit.endswith("}"):
                bit = bit[1:-1].strip()
                for v in self.variants:
                    if v["name"].upper() != bit.upper():
                        continue
                    bit = random.choice(v["variants"])
            o.append(bit)
        return "".join(o)
