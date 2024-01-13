import json
import os
import random
import re

from lib.utils import COC_ROOT_DIR, eval_dice

_treasure_library_cache = {}


def get_treasure_library(name):
    if name not in _treasure_library_cache:
        tl = TreasureLibrary(name=name)
        tl.load()
        _treasure_library_cache[name] = tl
    return _treasure_library_cache[name]


class TreasureLibrary:
    def __init__(self, name):
        self.name = name
        self.tables = []
        self.items = []
        self.variants = []

    def load(self):
        filename = os.path.join(
            COC_ROOT_DIR, "reference_info", "treasure", f"{self.name}.json"
        )
        with open(filename) as f:
            blob = json.load(f)
            self.tables = blob["tables"]
            self.items = blob["items"]
            self.variants = blob["variants"]

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
        contents = [x for x in contents if x]
        return contents

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
