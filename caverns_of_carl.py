"""Caverns of Carl

Vague plan of cool things
* room placement (done)
* connections/corridors (done)
* tts save file output (done)
* tts fog of war (done)
* stairs up & down (done)
* monster placement (done)
* treasure chests (done)
* tts fog of war with individual room coverage (done)
* monster encounter constraint: max_per_floor, Backline, Homogenous (done)
* double/triple wide hallways, double/triple doors (done)
* bookshelves (done)
* notecards per room/corridor (done)
* random traps in hallways or rooms (done)
* monster filter expressions, e.g. undead or "flesh golem" (done)
* UI in tkinter of some sort (done)
* monster encounter constraint: Frontline
* room lighting, denoted with floor tile tint & description
* cavernous levels
* DM toolpanel in TTS, including button to delete everything. Move health increment/decrement to this singleton object
* Prepared wandering monster encounters in the DM hidden zone (also relevant for traps that summon)
* GPT API integration?
* locked doors and keys?
* secret doors?
* themes and tilesets?
* rivers?
* altars?
* cosmetic doodads like wall sconces and bloodstains


TTS Dungeon or monster resources used:
https://steamcommunity.com/sharedfiles/filedetails/?id=375338382
https://steamcommunity.com/sharedfiles/filedetails/?id=2874146220
https://steamcommunity.com/sharedfiles/filedetails/?id=2917302184
https://steamcommunity.com/sharedfiles/filedetails/?id=2903159179
https://steamcommunity.com/sharedfiles/filedetails/?id=2300627680
https://aos-tts.github.io/Stormvault/
"""

import collections
import copy
import datetime
import functools
import json
import math
import os
import pathlib
import random
import re
import sys
import traceback

try:
    import tkinter as _tk_test
except:
    print(
        "Failed to load tcl/tk. You may need to install additional modules (e.g. python3-tk if you are on Ubuntu)\nPress enter to exit"
    )
    input()
    raise

import tkinter as tk
import tkinter.font
from tkinter import scrolledtext
from tkinter import ttk

_TTS_SPAWNED_TAG = "Terrain Object Spawned by Caverns of Carl"
_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))


def tts_default_save_location():
    if sys.platform == "linux" or sys.platform == "linux2":
        return os.path.join(
            str(pathlib.Path.home()),
            ".local",
            "share",
            "Tabletop Simulator",
            "Saves",
        )
    elif sys.platform == "darwin":  # mac osx
        return os.path.join(
            str(pathlib.Path.home()), "Library", "Tabletop Simulator", "Saves"
        )
    elif sys.platform == "win32":
        return os.path.join(
            os.environ["USERPROFILE"],
            "Documents",
            "My Games",
            "Tabletop Simulator",
            "Saves",
        )
    else:
        return f"couldn't match platform {sys.platform}, so don't know save game location"


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


_tts_reference_save_json_memoized = None
_seen_tts_guids = set()
_tts_reference_fog = None
_tts_reference_hidden_zone = None


def tts_reference_save_json():
    global _tts_reference_save_json_memoized
    if not _tts_reference_save_json_memoized:
        filename = os.path.join(
            _SCRIPT_DIR, "reference_info", "tts", "reference_save_file.json"
        )
        with open(filename) as f:
            _tts_reference_save_json_memoized = json.load(f)
            refresh_tts_guids(_tts_reference_save_json_memoized)
    return _tts_reference_save_json_memoized


def tts_reference_object_nicknames():
    return [o["Nickname"] for o in tts_reference_save_json()["ObjectStates"]]


def new_tts_guid():
    global _seen_tts_guids
    while True:
        guid = hex(random.randrange(16**5, 16**6))[2:8]
        if guid not in _seen_tts_guids:
            _seen_tts_guids.add(guid)
            return guid


def refresh_tts_guids(d):
    global _seen_tts_guids
    for k in d:
        v = k
        if isinstance(d, dict):
            v = d[k]
            if k == "GUID":
                if v not in _seen_tts_guids:
                    _seen_tts_guids.add(k)
                d[k] = new_tts_guid()
        if isinstance(v, dict) or isinstance(v, list):
            refresh_tts_guids(v)


def tts_reference_object(nickname):
    for o in tts_reference_save_json()["ObjectStates"]:
        if o["Nickname"] == nickname:
            return copy.deepcopy(o)
    raise KeyError(
        f"Could not find nickname '{nickname}' in tts reference game"
    )


def tts_fog(posX=0.0, posZ=0.0, scaleX=1.0, scaleZ=1.0, hidden_zone=False):
    global _tts_reference_fog, _tts_reference_hidden_zone
    if not _tts_reference_fog:
        ref_objs = tts_reference_save_json()["ObjectStates"]
        _tts_reference_fog = copy.deepcopy(
            [o for o in ref_objs if o["Name"] == "FogOfWar"][0]
        )
        _tts_reference_fog["Transform"] = {
            "posX": 0.0,
            "posY": 2.5,
            "posZ": 0.0,
            "rotX": 0.0,
            "rotY": 0.0,
            "rotZ": 0.0,
            "scaleX": 1.0,
            "scaleY": 3.5,
            "scaleZ": 1.0,
        }
        _tts_reference_fog["FogOfWar"]["Height"] = 1.0
    if not _tts_reference_hidden_zone:
        ref_objs = tts_reference_save_json()["ObjectStates"]
        _tts_reference_hidden_zone = copy.deepcopy(
            [o for o in ref_objs if o["Name"] == "FogOfWarTrigger"][0]
        )
        _tts_reference_hidden_zone["Transform"] = {
            "posX": 0.0,
            "posY": 2.5,
            "posZ": 0.0,
            "rotX": 0.0,
            "rotY": 0.0,
            "rotZ": 0.0,
            "scaleX": 1.0,
            "scaleY": 3.5,
            "scaleZ": 1.0,
        }
    if hidden_zone:
        fog = copy.deepcopy(_tts_reference_hidden_zone)
    else:
        fog = copy.deepcopy(_tts_reference_fog)
    fog["Transform"]["posX"] = posX
    fog["Transform"]["posZ"] = posZ
    fog["Transform"]["scaleX"] = scaleX
    fog["Transform"]["scaleZ"] = scaleZ
    return fog


class TTSFogBit:
    def __init__(
        self,
        x1,
        y1,
        x2=None,
        y2=None,
        roomixs=None,
        corridorixs=None,
        priority=1,
    ):
        if x2 is None:
            x2 = x1
        if y2 is None:
            y2 = y1
        self.x1 = min(x1, x2)
        self.y1 = min(y1, y2)
        self.x2 = max(x1, x2)
        self.y2 = max(y1, y2)
        self.roomixs = set(roomixs or [])
        self.corridorixs = set(corridorixs or [])
        self.priority = priority
        self.maximally_expanded = False

    def num_parents(self):
        return len(self.roomixs) + len(self.corridorixs)

    def coord_tuple(self):
        return (self.x1, self.y1, self.x2, self.y2)

    def merge_from_other(self, other):
        self.priority = max(self.priority, other.priority)
        self.roomixs = self.roomixs.union(other.roomixs)
        self.corridorixs = self.corridorixs.union(other.corridorixs)

    def tts_fog(self, df):
        x = (self.x1 + self.x2) / 2.0
        y = (self.y1 + self.y2) / 2.0
        posX = x - math.floor(df.width / 2.0) + 0.5
        posZ = y - math.floor(df.height / 2.0) + 0.5
        scaleX = 2 * (x - self.x1 + 0.5)
        scaleZ = 2 * (y - self.y1 + 0.5)
        return tts_fog(
            hidden_zone=True, posX=posX, posZ=posZ, scaleX=scaleX, scaleZ=scaleZ
        )

    def room_corridor_signature(self):
        return (tuple(sorted(self.roomixs)), tuple(sorted(self.corridorixs)))

    @staticmethod
    def merge_fog_bits(fog_bits):
        # Better merging maybe: https://mathoverflow.net/a/80676

        # room/corridor signature : list[bit]
        groups = collections.defaultdict(list)
        for bit in fog_bits:
            groups[bit.room_corridor_signature()].append(bit)
        output = []
        for l in groups.values():
            singletons = {(bit.x1, bit.y1): bit for bit in l}
            while len(singletons) > 0:
                # get the highest priority thing which isn't maximally expanded
                bit = None
                for x in singletons.values():
                    if bit is None or x.priority > bit.priority:
                        bit = x
                del singletons[(bit.x1, bit.y1)]
                for _ in range(500):
                    annex_coords = []
                    x1, x2, y1, y2 = bit.x1, bit.x2, bit.y1, bit.y2
                    dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
                    random.shuffle(dirs)
                    for dx, dy in dirs:
                        m = []
                        if dx < 0:
                            m = [(x1 + dx, y) for y in range(y1, y2 + 1)]
                        elif dx > 0:
                            m = [(x2 + dx, y) for y in range(y1, y2 + 1)]
                        elif dy < 0:
                            m = [(x, y1 + dy) for x in range(x1, x2 + 1)]
                        elif dy > 0:
                            m = [(x, y2 + dy) for x in range(x1, x2 + 1)]
                        if len(m) > sum([c in singletons for c in m]):
                            continue
                        if len(m) > len(annex_coords):
                            annex_coords = m
                    if len(annex_coords) < 1:
                        break
                    for x, y in annex_coords:
                        del singletons[(x, y)]
                        bit.x1 = min(bit.x1, x)
                        bit.x2 = max(bit.x2, x)
                        bit.y1 = min(bit.y1, y)
                        bit.y2 = max(bit.y2, y)
                output.append(bit)
        return output


class Tile:
    def __init__(self):
        self.trapixs = set()

    def to_char(self):
        return "?"

    def is_move_blocking(self):
        return True

    def is_feature(self):
        return False

    def is_ladder(self):
        return False

    def is_chest(self):
        return False


class WallTile(Tile):
    def __init__(self):
        pass

    def to_char(self):
        return "[0;37m#"

    def tts_object(self, df, x, y):
        obj = tts_reference_object("Wall, Dungeon")
        obj["Transform"]["rotY"] = 90.0 * random.randrange(4)
        obj["Nickname"] = ""
        return obj


class FloorTile(Tile):
    def tts_object(self, df, x, y):
        obj = tts_reference_object("Floor, Dungeon")
        obj["Transform"]["rotY"] = 90.0 * random.randrange(4)
        obj["Nickname"] = ""
        return obj

    def is_move_blocking(self):
        return False


class RoomFloorTile(FloorTile):
    def __init__(self, roomix):
        super().__init__()
        self.roomix = roomix

    def to_char(self):
        return "[0;37m."


class CorridorFloorTile(FloorTile):
    def __init__(self, corridorix):
        super().__init__()
        self.corridorix = corridorix

    def to_char(self):
        return "[0;37m,"


class DoorTile(CorridorFloorTile):
    def __init__(self, corridorix, doorix=None):
        super().__init__(corridorix)
        self.doorix = doorix

    def to_char(self):
        return "+"

    def tts_object(self, df, x, y):
        obj = None
        corridor = df.corridors[self.corridorix]
        door = df.doors[self.doorix]
        if corridor.width == 1:
            obj = tts_reference_object("Door, Metal")
            obj["Nickname"] = "Door"
        elif corridor.width == 2:
            if isinstance(df.tiles[x + 1][y], DoorTile) or isinstance(
                df.tiles[x][y - 1], DoorTile
            ):
                obj = tts_reference_object("Door, Double")
                obj["Nickname"] = "Large Door"
        else:
            if (
                isinstance(df.tiles[x + 1][y], DoorTile)
                and isinstance(df.tiles[x - 1][y], DoorTile)
                or isinstance(df.tiles[x][y + 1], DoorTile)
                and isinstance(df.tiles[x][y - 1], DoorTile)
            ):
                obj = tts_reference_object("Door, Triple")
                obj["Nickname"] = "Huge Door"
        if obj:
            for dx in [1, -1]:
                if isinstance(df.tiles[x + dx][y], RoomFloorTile):
                    obj["Transform"]["rotY"] = 90.0
        return obj

    def is_move_blocking(self):
        return True


class LadderUpTile(RoomFloorTile):
    def to_char(self):
        return "[1;97m<"

    def tts_object(self, df, x, y):
        obj = tts_reference_object("Ladder, Wood")
        # TODO: adjust such that ladder is against the wall if a wall is near
        obj["Transform"]["rotY"] = 90.0 * random.randrange(4)
        obj["Nickname"] = "Ladder up"
        return obj

    def is_move_blocking(self):
        return True

    def is_ladder(self):
        return True


class LadderDownTile(RoomFloorTile):
    def to_char(self):
        return "[1;97m>"

    def tts_object(self, df, x, y):
        obj = tts_reference_object("Floor, Hatch")
        obj["Transform"]["rotY"] = 90.0 * random.randrange(4)
        obj["Nickname"] = "Hatch down"
        return obj

    def is_move_blocking(self):
        return True

    def is_ladder(self):
        return True


def rotY_away_from_wall(df, x, y, original=0):
    posrots = [(0, 1, 0), (1, 0, 90), (0, -1, 180), (-1, 0, 270)]
    random.shuffle(posrots)
    for dx, dy, r in posrots:
        if isinstance(df.tiles[x + dx][y + dy], WallTile):
            return original + r
    return None


class ChestTile(RoomFloorTile):
    def __init__(self, roomix, contents=""):
        super().__init__(roomix)
        self.contents = contents

    def to_char(self):
        return "[1;93m$"

    def tts_object(self, df, x, y):
        obj = tts_reference_object("Chest Closed Tile")
        obj["Transform"]["rotY"] += rotY_away_from_wall(df, x, y)
        obj["Nickname"] = "Chest"
        obj["States"]["2"]["Nickname"] = "Open Chest"
        if self.contents:
            obj["States"]["2"]["Description"] = "Contents:\n" + self.contents
        return obj

    def is_move_blocking(self):
        return True

    def is_feature(self):
        return True

    def is_chest(self):
        return True


class BookshelfTile(ChestTile):
    def is_move_blocking(self):
        return False

    def to_char(self):
        return "[1;93mB"

    def tts_object(self, df, x, y):
        obj = tts_reference_object("Bookshelf Tile")
        # TODO: adjust to face away from wall if near wall
        obj["Transform"]["rotY"] += rotY_away_from_wall(df, x, y)
        obj["Nickname"] = "Bookshelf"
        obj["States"]["2"]["Nickname"] = "Examined Bookshelf"
        if self.contents:
            obj["States"]["2"]["Description"] = "Contents:\n" + self.contents
        return obj


class MimicTile(ChestTile):
    def __init__(self, roomix, monster):
        super().__init__(roomix, contents="")
        self.monster = monster

    def to_char(self):
        return "m"

    def tts_object(self, df, x, y):
        obj = tts_reference_object("Chest Closed Mimic Tile")
        obj["Transform"]["rotY"] += rotY_away_from_wall(df, x, y)
        obj["Nickname"] = "Chest"
        obj["States"]["2"]["Nickname"] = "It's a Mimic!"
        obj["States"]["2"]["ChildObjects"][0][
            "Nickname"
        ] = self.monster.tts_nickname()
        return obj


_monster_library_cache = {}
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
            _SCRIPT_DIR, "reference_info", "treasure", f"{self.name}.json"
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
            _SCRIPT_DIR, "reference_info", "treasure", f"{self.name}.json"
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


def get_monster_library(name):
    if name not in _monster_library_cache:
        ml = MonsterLibrary(name=name)
        ml.load()
        _monster_library_cache[name] = ml
    return _monster_library_cache[name]


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


class MonsterLibrary:
    def __init__(self, name):
        self.name = name
        self.monster_infos = []

    def load(self):
        filename = os.path.join(
            _SCRIPT_DIR, "reference_info", "monsters", f"{self.name}.json"
        )
        with open(filename) as f:
            blob = json.load(f)
            for monster_blob in blob["monsters"]:
                self.monster_infos.append(MonsterInfo(monster_blob))

    def to_blob(self):
        return {
            "name": self.name,
            "monsters": [x.to_blob() for x in self.monster_infos],
        }

    def save(self):
        filename = os.path.join(
            _SCRIPT_DIR, "reference_info", "monsters", f"{self.name}.json"
        )
        with open(filename, "w") as f:
            json.dump(self.to_blob(), f, indent=2)

    @staticmethod
    def monster_matches_expr(expr, monster_info):
        tokens = []
        if isinstance(expr, list):
            tokens = expr
        else:
            tokens = re.split("([()]| OR | AND )", expr.upper())
            tokens = [x.strip() for x in tokens]
            tokens = [x for x in tokens if x]
        if "(" in tokens:  # gotta group up those parens
            pass
        re.split("(")
        if "(" in expr:
            cur = [None]  # parent, thing thing thing
            root = cur
            for ix, c in enumerate(expr):
                if c == "(":
                    deeper = []
                    cur.append(deeper)
                    cur = deeper

        pass

    def get_monster_infos(
        self,
        filter=None,
        min_challenge_rating=None,
        max_challenge_rating=None,
        has_tts=False,
    ):
        output = []
        for m in self.monster_infos:
            if has_tts and len(m.tts_reference_nicknames) < 1:
                continue
            if filter is not None:
                if not expr_match_keywords(filter, [m.name] + m.keywords):
                    continue
            if min_challenge_rating is not None:
                if (
                    m.challenge_rating is None
                    or m.challenge_rating < min_challenge_rating
                ):
                    continue
            if max_challenge_rating is not None:
                if (
                    m.challenge_rating is None
                    or m.challenge_rating > max_challenge_rating
                ):
                    continue
            output.append(m)
        return output


class MonsterInfo:
    def __init__(self, blob={}):
        self.name = blob.get("name", "Unnamed Monster")
        self.keywords = blob.get("keywords", [])
        self.tts_reference_nicknames = blob.get("tts_reference_nicknames", [])
        self.ascii_char = blob.get("ascii_char", "e")
        self.health = blob.get("health")
        self.hit_dice_formula = blob.get("hit_dice_formula")
        self.size = blob.get("size")
        self.diameter = blob.get("diameter", 1)
        self.synergies = blob.get("synergies", [])
        self.challenge_rating = blob.get("challenge_rating")
        self.xp = blob.get("xp")
        self.max_per_floor = blob.get("max_per_floor")
        self.frequency = blob.get("frequency", 1.0)

    def to_blob(self):
        return self

    def has_keyword(self, k):
        for k2 in self.keywords:
            if k.upper() == k2.upper():
                return True
        return False

    def has_keyword_or_name(self, kn):
        return self.name.upper() == kn.upper() or self.has_keyword(kn)


class Monster:
    def __init__(
        self, monster_info, name=None, health=None, x=0, y=0, roomix=None
    ):
        self.monster_info = monster_info
        self.name = name or self.monster_info.name
        self.health = health
        if health:
            self.health = health
        elif monster_info.hit_dice_formula:
            self.health = eval_dice(monster_info.hit_dice_formula)
        else:
            self.health = monster_info.health
        self.x = x
        self.y = y
        self.roomix = roomix
        self.ix = None

    def to_char(self):
        return self.monster_info.ascii_char

    def adjust_cr(self, new_cr):
        dmg_hps = {
            0: 3.5,
            0.125: 21.0,
            0.25: 42.5,
            0.5: 60.0,
            1: 78.0,
            2: 93.0,
            3: 108.0,
            4: 123.0,
            5: 138.0,
            6: 153.0,
            7: 168.0,
            8: 183.0,
            9: 198.0,
            10: 213.0,
            11: 228.0,
            12: 243.0,
            13: 258.0,
            14: 273.0,
            15: 288.0,
            16: 303.0,
            17: 318.0,
            18: 333.0,
            19: 348.0,
            20: 378.0,
            21: 423.0,
            22: 468.0,
            23: 513.0,
            24: 558.0,
            25: 603.0,
            26: 648.0,
            27: 693.0,
            28: 738.0,
            29: 783.0,
            30: 828.0,
        }
        xps = {
            0: 10,
            0.125: 25,
            0.25: 50,
            0.5: 100,
            1: 200,
            2: 450,
            3: 700,
            4: 1100,
            5: 1800,
            6: 2300,
            7: 2900,
            8: 3900,
            9: 5000,
            10: 5900,
            11: 7200,
            12: 8400,
            13: 10000,
            14: 11500,
            15: 13000,
            16: 15000,
            17: 18000,
            18: 20000,
            19: 22000,
            20: 25000,
            21: 33000,
            22: 41000,
            23: 50000,
            24: 62000,
            25: 75000,
            26: 90000,
            27: 105000,
            28: 120000,
            29: 135000,
            30: 155000,
        }
        old_cr = self.monster_info.challenge_rating
        if new_cr == old_cr:
            return
        self.monster_info = copy.deepcopy(self.monster_info)
        self.monster_info.challenge_rating = new_cr
        self.monster_info.xp = round(
            self.monster_info.xp * xps[new_cr] / xps[old_cr]
        )
        if self.health:
            self.health = max(
                1, round(self.health * dmg_hps[new_cr] / dmg_hps[old_cr])
            )
        if self.name:
            self.name = re.sub(r" \(CR [0-9]+\)", "", self.name)
            fractionator = {0.125: "1/8", 0.25: "1/4", 0.5: "1/2"}
            new_cr = fractionator.get(new_cr, new_cr)
            self.name = self.name + f" (CR {new_cr})"

    def tts_nickname(self):
        s = self.name or "Unnamed Monster"
        if self.health:
            s = f"{self.health}/{self.health} {s}"
        return s

    def tts_object(self, df):
        ref_nick = self.monster_info.tts_reference_nicknames[
            random.randrange(len(self.monster_info.tts_reference_nicknames))
        ]
        obj = tts_reference_object(ref_nick)
        obj["Transform"]["posX"] = self.x - math.floor(df.width / 2.0) + 0.5
        obj["Transform"]["posY"] = 2.0
        obj["Transform"]["posZ"] = self.y - math.floor(df.height / 2.0) + 0.5
        if self.monster_info.diameter == 2:
            # offset for wider models
            obj["Transform"]["posX"] += 0.5
            obj["Transform"]["posZ"] += 0.5
        # TODO: adjust to not face wall if near wall?
        obj["Transform"]["rotY"] = 90.0 * random.randrange(4)
        obj["Nickname"] = self.tts_nickname()
        return obj


_AREA_TRAP_TRIGGERS = [
    "Scattered pressure plates",
    "Magical chalk lines",
    "Life-sensing runes",
]
_CORRIDOR_TRAP_TRIGGERS = [
    "Tripwire by the door",
    "Tripwire midway through",
    "Pressure plates by the door",
]
_ONE_OFF_DAMAGE_TRAP_EFFECTS = [
    "Swinging blade: {AB} to hit, {DAM:slashing}",
    "Poison darts: {AB} to hit, {DAM:piercing} & {DAM:poison}",
    "Extending spikes: {AB} to hit, {DAM:piercing}",
    "Falling rocks: Dex {DC} to avoid, {DAM:bludgeoning}",
    "Flame jet: Dex {DC} for half, {DAM:fire}",
    "Fiery explosion, {AREA}: Dex {DC} for half, {DAM:fire}",
    "Flash freeze, {AREA}: Con {DC} for half, {DAM:cold}",
    "Acid spray, {AREA}: Dex {DC} for half, {DAM:acid}",
    "Thunderous shockwave, {AREA}: Con {DC} for half, {DAM:thunder}",
    "Life drain, {AREA}: Con {DC} for half, {DAM:necrotic}",
    "Mind-shattering scream, {AREA}: Int {DC} for half, {DAM:psychic}",
]
_SLOW_DAMAGE_TRAP_EFFECTS = [
    "Poison gas fills the area: Start turn, Con {DC} to resist, {DAM:poison,slow}",
    "Acidic mist fills the area: Start turn, Con {DC} to resist, {DAM:acid,slow}",
    "Electrified floor in the area: Start turn, Con {DC} to resist, {DAM:lightning,slow}",
    "Oven-hot area: Start turn, Con {DC} to resist, {DAM:fire,slow}",
]
_MISC_TRAP_EFFECTS = [
    "Thunderous Alarm: alerts nearby rooms' enemies",
    # Future: summon monsters (once we get wanding monsters)
]
_MISC_ROOM_OR_CORRIDOR_TRAP_EFFECTS = [
    "Reverse Gravity (PHB 272): Fills location. Dex {DC} to grab onto something. Ceiling spikes {DAM:piercing}",
    "Various tiles collapse into quicksand: Dex {DC} to avoid. Start turn {DAM:bludgeoning,slow},  Str (Ath) {DC} to get out",
]
_MISC_CORRIDOR_TRAP_EFFECTS = [
    "Doors shut and lock: Str(Ath) or Arcana or Thieves' Tools {DC}. {SLOW_DAMAGE_TRAP_EFFECT}",
    "Doors shut and lock: Str(Ath) or Arcana or Thieves' Tools {DC}. Repeated Con {DC-2}; fail 3 and get infected with {DISEASE}",
    "Doors open; Gust of wind, Str {DC} or {DAM:bludgeoning,slow} and be pushed 10' and prone (ideally towards danger)",
    "Doors open; {SHORT_DEBUFF_TRAP_EFFECT} (only if nearby enemies)"
    "Doors open; A Watery Sphere spell (XGE 170), Str {DC}, moves from one end of corridor to other (ideally towards danger)",
    "Corridor filled with ever-swinging pendulum blades. Each turn moving through requires Dex (Acro) {DC} or take {DAM:slashing}, Dex {DC} for half. Must also save on forced movement. Disadvantage if you dash or move more than half speed. Can Int (Investigation) {DC} as an action to gain advantage on your next move.",
]
_SHORT_DEBUFF_TRAP_EFFECTS = [
    "Blindness spell (PHB 219): {AREA}, Con {DC}",
    "Confusion spell (PHB 224): {AREA}, Wis {DC}",
    # "Divine Word spell (PHB 234): {AREA}, Wis {DC}",
    "Evard's Black Tentacles (PHB 238): {AREA}, Dex/Str {DC}, {DAM:bludgeoning,slow}",
    "Faerie Fire spell (PHB 239): {AREA}, Dex {DC}",
    "Polymorph spell (PHB 287): {AREA}, Wis {DC-2}, Crab",
    "Psychic Scream spell (XGE 163): {AREA}, Int {DC-2}, {DAM:psychic}",
    "Slow spell (PHB 277): {AREA}, Wis {DC}",
    "Web spell (PHB 287): {AREA}, Dex/Str {DC}",
]
_MEDIUM_DEBUFF_TRAP_EFFECTS = [
    # "Curse: Wis {DC}, {CURSE}",
    "Curse of Silence: Wis {DC}, can't talk for 1 hour",
    "Reduce spell (PHB 237): Con {DC}, 1 hour",
]
_LONG_DEBUFF_TRAP_EFFECTS = [
    # "Curse: Wis {DC}, {CURSE}",
    "Contagion spell (PHB 227): Con {DC}, {DISEASE}",
    # "Flesh to Stone spell (PHB 243): Con {DC} {MIN_LEVEL:11}",
]
_DISEASES = [
    "Blinding Sickness (PHB 227)",
    "Cackle Fever (DMG 257)",
    "Filth Fever (PHB 227)",
    "Flesh Rot (PHB 227)",
    "Mindfire (PHB 227)",
    "Seizure (PHB 227)",
    "Sewer Plague (DMG 257)",
    "Sight Rot (DMG 257)",
    "Slimy Doom (PHB 227)",
]
_DAMAGE_TYPE_DEFAULT_DICE = collections.defaultdict(lambda: 6)
_DAMAGE_TYPE_DEFAULT_DICE["acid"] = 4
_DAMAGE_TYPE_DEFAULT_DICE["poison"] = 8
_DAMAGE_TYPE_DEFAULT_DICE["cold"] = 8


class Trap:
    def __init__(self, config):
        self.config = config
        self.level = config.target_character_level
        self.notice_dc = self.random_dc()
        self.disarm_dc = self.random_dc()
        self.trigger = ""
        self.effect = ""
        self.corridorix = None
        self.roomIx = None

    def description(self):
        return f"Trap (find DC:{self.notice_dc}, disarm DC:{self.disarm_dc})\nTrigger: {self.trigger}\n{self.effect}"

    def eval_trap_expr(self, s):
        num_dams = len(re.findall("({DAM[^}]*})", s))
        o = []
        for bit in re.split("({[^}]+})", s):
            if bit.startswith("{") and bit.endswith("}"):
                bit = bit[1:-1].strip()
                mods = set()
                cmd = bit
                if ":" in bit:
                    cmd, mod_s = bit.split(":")
                    mods = set(mod_s.split(","))
                if cmd.upper() == "DISEASE":
                    o.append(random.choice(_DISEASES))
                elif cmd.upper().startswith("DC"):
                    dc = self.random_dc()
                    if len(cmd) > 2:
                        dc = int(eval(f"({dc}){cmd[2:]}"))
                    o.append(f"DC:{dc}")
                elif cmd.upper().startswith("AB"):
                    ab = self.random_hit_bonus()
                    if len(cmd) > 2:
                        ab = int(eval(f"({ab}){cmd[2:]}"))
                    if ab >= 0:
                        ab = f"+{ab}"
                    else:
                        ab = f"{ab}"
                    o.append(ab)
                elif cmd.upper() == "AREA":
                    o.append(self.random_area())
                elif cmd.upper() == "DAM":
                    slow = False
                    if "slow" in mods:
                        slow = True
                        mods.remove("slow")
                    avg_dam = self.random_avg_damage(slow=slow) / num_dams
                    dtype = "force"
                    if mods:
                        dtype = mods.pop()
                    d = _DAMAGE_TYPE_DEFAULT_DICE[dtype]
                    dice = self.random_damage_dice_expr(d, avg_dam)
                    o.append(f"{dice} {dtype} damage")
                elif cmd.upper() == "SHORT_DEBUFF_TRAP_EFFECT":
                    n = random.randrange(len(_SHORT_DEBUFF_TRAP_EFFECTS))
                    eff = _SHORT_DEBUFF_TRAP_EFFECTS[n]
                    o.append(self.eval_trap_expr(eff))
                elif cmd.upper() == "SLOW_DAMAGE_TRAP_EFFECT":
                    n = random.randrange(len(_SLOW_DAMAGE_TRAP_EFFECTS))
                    eff = _SLOW_DAMAGE_TRAP_EFFECTS[n]
                    o.append(self.eval_trap_expr(eff))
            else:
                o.append(bit)
        return "".join(o)

    def random_area(self):
        radius = 5 * random.randrange(1, int(self.level / 5) + 4)
        return f"{radius}' radius"

    def random_dc(self):
        lo = int(math.floor(self.level * 0.7 + 8))
        hi = int(math.ceil(self.level * 0.8 + 12))
        return random.randrange(lo, hi)

    def random_hit_bonus(self):
        mid = self.level * 0.65 + 2.5
        plusminus = 2 + self.level / 10.0
        b = mid + random.random() * plusminus * 2 - plusminus
        return int(round(b))

    def random_avg_damage(self, slow=False):
        lo = self.level * 3
        hi = self.level * 8
        if slow:
            return random.randrange(lo, hi) / 4.0
        return random.randrange(lo, hi)

    def random_damage_dice_expr(self, d, target_avg=None):
        if target_avg is None:
            target_avg = self.random_avg_damage()
        if target_avg < d / 2 - 1:
            if target_avg <= 1:
                return "1"
            elif target_avg <= 3:
                return "1d4"
            elif target_avg <= 4:
                return "1d6"
            elif target_avg <= 5:
                return "1d8"
            elif target_avg <= 6:
                return "1d10"
            else:
                return "1d12"
        return f"{max(1, int(round(target_avg / (d/2.0+0.5))))}d{d}"


class ChestTrap(Trap):
    def __init__(self, config, x, y):
        super().__init__(config)
        self.x = x
        self.y = y

    def description(self):
        return "Chest " + super().description()

    @staticmethod
    def create(config, x, y):
        trap = ChestTrap(config, x, y)
        trap.trigger = "Opening or tampering"
        effs = (
            _ONE_OFF_DAMAGE_TRAP_EFFECTS
            + _MISC_TRAP_EFFECTS
            + _MEDIUM_DEBUFF_TRAP_EFFECTS
            + _LONG_DEBUFF_TRAP_EFFECTS
        )
        trap.effect = trap.eval_trap_expr(random.choice(effs))
        return trap


class RoomTrap(Trap):
    def __init__(self, config, roomix):
        super().__init__(config)
        self.roomix = roomix

    def description(self):
        return "Room " + super().description()

    @staticmethod
    def create(config, roomix):
        trap = RoomTrap(config, roomix)
        tgs = _AREA_TRAP_TRIGGERS
        trap.trigger = random.choice(tgs)
        effs = (
            _ONE_OFF_DAMAGE_TRAP_EFFECTS
            + _SLOW_DAMAGE_TRAP_EFFECTS
            + _MISC_TRAP_EFFECTS
            + _MISC_ROOM_OR_CORRIDOR_TRAP_EFFECTS
        )
        trap.effect = trap.eval_trap_expr(random.choice(effs))
        return trap

    def random_area(self):
        if random.randrange(2):
            return super().random_area()
        else:
            return "whole room"


class CorridorTrap(Trap):
    def __init__(self, config, corridorix):
        super().__init__(config)
        self.corridorix = corridorix

    def description(self):
        return "Corridor " + super().description()

    @staticmethod
    def create(config, corridorix):
        trap = CorridorTrap(config, corridorix)
        tgs = _AREA_TRAP_TRIGGERS + _CORRIDOR_TRAP_TRIGGERS
        trap.trigger = random.choice(tgs)
        effs = (
            _ONE_OFF_DAMAGE_TRAP_EFFECTS
            + _MISC_CORRIDOR_TRAP_EFFECTS
            + _MISC_TRAP_EFFECTS
            + _MISC_ROOM_OR_CORRIDOR_TRAP_EFFECTS
        )
        trap.effect = trap.eval_trap_expr(random.choice(effs))
        return trap

    def random_area(self):
        if random.randrange(2):
            return super().random_area()
        else:
            return "whole corridor"


class DoorTrap(Trap):
    def __init__(self, config, doorix, x, y):
        super().__init__(config)
        self.doorix = doorix
        self.x = x
        self.y = y

    def description(self):
        return "Door " + super().description()

    @staticmethod
    def create(config, corridorix, x, y):
        trap = DoorTrap(config, corridorix, x, y)
        trap.trigger = "Opening or tampering"
        effs = _ONE_OFF_DAMAGE_TRAP_EFFECTS + _MISC_TRAP_EFFECTS
        trap.effect = trap.eval_trap_expr(random.choice(effs))
        return trap


class Room:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.has_up_ladder = False
        self.has_down_ladder = False
        self.ix = None
        self.encounter = None
        self.doorixs = set()
        self.trapixs = set()

    def apply_to_tiles(self, tiles):
        raise NotImplementedError()

    def remove_from_tiles(self, tiles):
        raise NotImplementedError()

    def tile_coords(self):
        raise NotImplementedError()

    def has_ladder(self):
        return self.has_up_ladder or self.has_down_ladder

    def pick_tile(
        self,
        df,
        roomix,
        unoccupied=False,
        avoid_corridor=False,
        prefer_wall=False,
        avoid_wall=False,
        diameter=1,
    ):
        raise NotImplementedError()

    def total_space(self):
        raise NotImplementedError()

    def description(self, df, verbose=False):
        o = []
        if self.has_down_ladder:
            o.append("Down ladder")
        if self.has_up_ladder:
            o.append("Up ladder")
        for trapix in self.trapixs:
            o.append(df.traps[trapix].description())
        if verbose:
            if self.encounter:
                xp = self.encounter.total_xp()
                pct = int(round(100.0 * xp / med_target_xp(df.config)))
                s = [f"Monster encounter (~{xp} xp; ~{pct}% of Medium):"]
                s.append(self.encounter.description())
                o.append("\n".join(s))
            for doorix in self.doorixs:
                door = df.doors[doorix]
                corridor = df.corridors[door.corridorix]
                other_roomix = (
                    set([corridor.room1ix, corridor.room2ix]) - set([self.ix])
                ).pop()
                s = f"Door to Room {other_roomix}"
                if corridor.is_nontrivial(df):
                    s += f" by way of Corridor {corridor.name}"
                for trapix in door.trapixs:
                    s += "\n" + df.traps[trapix].description()
                o.append(s)
            for x, y in self.tile_coords():
                tile = df.tiles[x][y]
                if isinstance(tile, MimicTile):
                    o.append("Mimic chest!")
                    continue
                elif not isinstance(tile, ChestTile):
                    continue
                s = ["Chest ([1;93m$):"]
                if isinstance(tile, BookshelfTile):
                    s = ["Bookshelf ([1;93mB):"]
                for trapix in tile.trapixs:
                    s.append(df.traps[trapix].description())
                if tile.contents.strip() == "Nothing!":
                    s.append("Empty")
                else:
                    s.append(tile.contents)
                o.append("\n".join(s))
        if not o:
            return "Nothing special"
        return "\n\n".join(o)

    def tts_notecard(self, df):
        obj = tts_reference_object("Reference Notecard")
        obj["Nickname"] = f"DM/GM notes for room {self.ix}"
        obj["Description"] = self.description(df)
        obj["Transform"]["posY"] = 4.0
        obj["Locked"] = True
        df.tts_xz(self.x, self.y, obj)
        return obj


class RectRoom(Room):
    def __init__(self, x, y, rw=1, rh=1):
        super().__init__(x, y)
        self.rw = rw
        self.rh = rh

    def embiggened(self):
        return RectRoom(
            self.x,
            self.y,
            self.rw + random.randrange(2),
            self.rh + random.randrange(2),
        )

    def wiggled(self):
        return RectRoom(
            self.x + random.randrange(-1, 2),
            self.y + random.randrange(-1, 2),
            self.rw,
            self.rh,
        )

    def apply_to_tiles(self, tiles):
        for x in range(self.x - self.rw, self.x + self.rw + 1):
            for y in range(self.y - self.rh, self.y + self.rh + 1):
                tiles[x][y] = RoomFloorTile(self.ix)

    def remove_from_tiles(self, tiles):
        for x in range(self.x - self.rw, self.x + self.rw + 1):
            for y in range(self.y - self.rh, self.y + self.rh + 1):
                tiles[x][y] = WallTile()

    def tile_coords(self):
        for x in range(self.x - self.rw, self.x + self.rw + 1):
            for y in range(self.y - self.rh, self.y + self.rh + 1):
                yield (x, y)

    def pick_tile(
        self,
        df,
        roomix,
        unoccupied=False,
        avoid_corridor=False,
        prefer_wall=False,
        avoid_wall=False,
        diameter=1,
    ):
        for _ in range(100):
            x = self.x
            y = self.y
            if prefer_wall:
                # TODO: fix this for wider diameters
                if random.randrange(2) == 0:
                    x += self.rw * (random.randrange(2) * 2 - 1)
                    y += random.randrange(-self.rh, self.rh + 1)
                else:
                    x += random.randrange(-self.rw, self.rw + 1)
                    y += self.rh * (random.randrange(2) * 2 - 1)
            elif avoid_wall:
                # TODO: fix this for wider diameters
                x += random.randrange(-self.rw + 1, self.rw)
                y += random.randrange(-self.rh + 1, self.rh)
            else:
                x += random.randrange(-self.rw, self.rw + 1)
                y += random.randrange(-self.rh, self.rh + 1)

            found_problem = False
            coords_to_check = [(x, y)]
            if diameter == 2:
                coords_to_check = [
                    (x + dx, y + dy) for dx in [0, 1] for dy in [0, 1]
                ]
            elif diameter == 3:
                coords_to_check = [
                    (x + dx, y + dy) for dx in [-1, 0, 1] for dy in [-1, 0, 1]
                ]
            for tx, ty in coords_to_check:
                if unoccupied and (tx, ty) in df.monster_locations:
                    found_problem = True
                    break
                tile = df.tiles[tx][ty]
                if unoccupied and tile.is_move_blocking() or tile.is_feature():
                    found_problem = True
                    break

                if avoid_corridor or prefer_wall or avoid_wall:
                    found_corridor = False
                    found_wall = False
                    for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                        dtile = df.tiles[tx + dx][ty + dy]
                        if isinstance(dtile, CorridorFloorTile):
                            found_corridor = True
                        if isinstance(dtile, DoorTile):
                            found_corridor = True
                        if isinstance(dtile, WallTile):
                            found_wall = True
                    if found_corridor and avoid_corridor:
                        found_problem = True
                    if found_wall and avoid_wall:
                        found_problem = True
                    if not found_wall and prefer_wall:
                        found_problem = True
            if not found_problem:
                return (x, y)
        return None

    def total_space(self):
        return (1 + self.rw * 2) * (1 + self.rh * 2)

    def tts_fog_bits(self, roomix):
        """returns a list of fog bits: a big central one, and a small one for each border grid space."""
        x1 = self.x - self.rw
        y1 = self.y - self.rh
        x2 = self.x + self.rw
        y2 = self.y + self.rh
        fogs = []
        # central_fog = TTSFogBit(x1, y1, x2, y2, roomixs=[roomix])
        # fogs = [central_fog]
        # border bits:
        for x in range(x1 - 1, x2 + 2):
            for y in range(y1 - 1, y2 + 2):
                # if x != x1-1 and x != x2+1 and y != y1 - 1 and y != y2 + 1:
                #     continue
                priority = 1
                if x == self.x and y == self.y:
                    priority = 2
                fogs.append(
                    TTSFogBit(x, y, roomixs=[roomix], priority=priority)
                )
        return fogs


class CorridorWalker:
    def __init__(self, corridor, max_width_iter=None):
        self.corridor = corridor
        self.width_iter = 0
        self.max_width_iter = max_width_iter
        if max_width_iter is None:
            self.max_width_iter = corridor.width
        self._initialize()

    def __iter__(self):
        return self

    def _initialize(self):
        self.x = self.corridor.x1
        self.y = self.corridor.y1
        self.x2 = self.corridor.x2
        self.y2 = self.corridor.y2
        dx = int(math.copysign(1, self.corridor.x2 - self.corridor.x1))
        dy = int(math.copysign(1, self.corridor.y2 - self.corridor.y1))
        self.going_horizontal = self.corridor.is_horizontal_first
        if self.width_iter == 1:
            if self.going_horizontal:
                self.y += dy
                self.x2 -= dx
            else:
                self.x += dx
                self.y2 -= dy
        elif self.width_iter == 2:
            if self.going_horizontal:
                self.y -= dy
                self.x2 += dx
            else:
                self.x -= dx
                self.y2 += dy

    def __next__(self):
        if self.x == self.x2 and self.y == self.y2:
            self.width_iter += 1
            if self.width_iter >= self.max_width_iter:
                raise StopIteration
            self._initialize()
        if self.x == self.x2 and self.going_horizontal:
            self.going_horizontal = False
        if self.y == self.y2 and not self.going_horizontal:
            self.going_horizontal = True
        if self.going_horizontal:
            if self.x2 > self.x:
                self.x += 1
            else:
                self.x -= 1
        else:
            if self.y2 > self.y:
                self.y += 1
            else:
                self.y -= 1
        return (self.x, self.y)


class Corridor:
    def __init__(
        self, room1ix, room2ix, x1, y1, x2, y2, is_horizontal_first, width=1
    ):
        self.room1ix, self.room2ix = room1ix, room2ix
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.is_horizontal_first = is_horizontal_first
        self.width = width
        self.ix = None
        self.doorixs = set()
        self.trapixs = set()
        self.name = None

    def walk(self, max_width_iter=None):
        return CorridorWalker(self, max_width_iter=max_width_iter)

    def is_nontrivial(self, df):
        usable_length = 0.0
        for x, y in self.walk():
            tile = df.tiles[x][y]
            if isinstance(tile, CorridorFloorTile) and not isinstance(
                tile, DoorTile
            ):
                usable_length += 1.0 / self.width
        return usable_length > 2.5

    def description(self, df, verbose=False):
        o = []
        for trapix in self.trapixs:
            o.append(df.traps[trapix].description())
        if verbose:
            for doorix in self.doorixs:
                door = df.doors[doorix]
                assert len(door.roomixs) == 1
                roomix = list(door.roomixs)[0]
                s = f"Door to Room {roomix}"
                for trapix in door.trapixs:
                    s += "\n" + df.traps[trapix].description()
                o.append(s)
        if not o:
            return "Nothing special"
        return "\n\n".join(o)

    def tts_notecard(self, df):
        obj = tts_reference_object("Reference Notecard")
        obj["Nickname"] = f"DM/GM notes for corridor {self.name}"
        obj["Description"] = self.description(df)
        obj["Transform"]["posY"] = 4.0
        obj["Locked"] = True
        x, y = self.middle_coords(df)
        df.tts_xz(x, y, obj)
        return obj

    def middle_coords(self, df):
        """
        Attempts to find the midpoint(ish) of the corridor's tunnel.
        Returns a pair (x, y) of that point's coordinates.
        Raises RuntimeError in pathological cases (corridors which did not go through walls; won't happen in practice).
        """
        in_corridor = False
        corridor_coords = []
        for x, y in self.walk():
            if isinstance(df.tiles[x][y], CorridorFloorTile):
                in_corridor = True
                corridor_coords.append((x, y))
            else:
                if in_corridor:
                    break  # we just left the corridor
        if not corridor_coords:
            raise RuntimeError("Corridor with no corridor tiles!?")
        return corridor_coords[round(len(corridor_coords) / 2)]

    def door_coords(self, df):
        """
        Returns a list of pairs (x, y) of coordinates of the
        corridor's doors. This only produces one result for a
        double/triple wide door; if the caller needs those tiles,
        should examine nearby tiles.
        """
        in_corridor = False
        door_coords = []
        for x, y in self.walk():
            tile = df.tiles[x][y]
            if isinstance(tile, DoorTile):
                door_coords.append((x, y))
            if isinstance(tile, CorridorFloorTile):
                in_corridor = True
            else:
                if in_corridor:
                    break  # we just left the corridor
        return door_coords

    def tts_fog_bits(self, df, corridorix):
        """returns a list of fog bits: all small ones probably."""
        fogs = []
        num_blank_corridor_tiles = 0
        # walked places
        for x, y in self.walk():
            tile = df.tiles[x][y]
            if isinstance(tile, CorridorFloorTile):
                if not isinstance(tile, DoorTile):
                    num_blank_corridor_tiles += 1
                fogs.append(TTSFogBit(x, y, corridorixs=[corridorix]))
                for dx in [-1, 1]:
                    for dy in [-1, 1]:
                        if isinstance(df.tiles[x + dx][y + dy], WallTile):
                            fogs.append(
                                TTSFogBit(
                                    x + dx, y + dy, corridorixs=[corridorix]
                                )
                            )
        if num_blank_corridor_tiles == 0:
            return []
        return fogs


class Door:
    def __init__(self, x, y, corridorix, roomixs=None):
        self.x, self.y = x, y
        self.corridorix = corridorix
        self.roomixs = set(roomixs or [])
        self.trapixs = set()
        self.ix = None


class DungeonFloor:
    def __init__(self, config):
        self.config = config
        self.width = config.width
        self.height = config.height
        # tiles[x][y] points to a tile on the map. Indexed [0, width) and [0, height)
        self.tiles = [
            [WallTile() for y in range(self.height)] for x in range(self.width)
        ]
        self.rooms = []
        self.corridors = []
        self.doors = []
        self.monsters = []
        self.traps = []
        self.monster_locations = {}  # (x, y) -> monster
        self.room_neighbors = collections.defaultdict(set)

    def tts_xz(self, x, y, tts_transform=None):
        tts_x = x - math.floor(self.width / 2.0) + 0.5
        tts_z = y - math.floor(self.height / 2.0) + 0.5
        if tts_transform:
            if "Transform" in tts_transform:
                tts_transform = tts_transform["Transform"]
            tts_transform["posX"] = tts_x
            tts_transform["posZ"] = tts_z
        return (tts_x, tts_z)

    def random_room(self):
        r = int(max(1, self.config.min_room_radius))
        return RectRoom(
            x=random.randrange(2, self.width - 2),
            y=random.randrange(2, self.height - 2),
            rw=r,
            rh=r,
        )

    def add_room(self, room):
        room.ix = len(self.rooms)
        self.rooms.append(room)
        room.apply_to_tiles(self.tiles)

    def add_corridor(self, corridor):
        corridor.ix = len(self.corridors)
        self.corridors.append(corridor)
        self.room_neighbors[corridor.room1ix].add(corridor.room2ix)
        self.room_neighbors[corridor.room2ix].add(corridor.room1ix)
        for x, y in corridor.walk():
            if isinstance(self.tiles[x][y], WallTile):
                self.tiles[x][y] = CorridorFloorTile(corridor.ix)

    def add_door(self, door):
        door.ix = len(self.doors)
        self.doors.append(door)

    def add_monster(self, monster):
        monster.ix = len(self.monsters)
        self.monsters.append(monster)
        x, y = monster.x, monster.y
        monster_coords = [(x, y)]
        if monster.monster_info.diameter == 2:
            monster_coords = [
                (x + dx, y + dy) for dx in [0, 1] for dy in [0, 1]
            ]
        elif monster.monster_info.diameter == 3:
            monster_coords = [
                (x + dx, y + dy) for dx in [-1, 0, 1] for dy in [-1, 0, 1]
            ]
        for mx, my in monster_coords:
            self.monster_locations[(mx, my)] = monster

    def add_trap(self, trap):
        trap.ix = len(self.traps)
        self.traps.append(trap)

    def ascii(self, colors=False):
        chars = [
            [self.tiles[x][y].to_char() for y in range(self.height)]
            for x in range(self.width)
        ]
        for monster in self.monsters:
            chars[monster.x][monster.y] = monster.to_char()
        for room in self.rooms:
            num_s = str(room.ix)
            x, y = room.x, room.y
            x -= (len(num_s) - 1) / 2.0
            # Try to avoid locations that have stuff on them
            ok_positions = []
            for tx, ty in room.tile_coords():
                is_ok = True
                for ix in range(len(num_s)):
                    if not chars[tx + ix][ty].endswith("."):
                        is_ok = False
                        break
                if is_ok:
                    ok_positions.append((tx, ty))
            if ok_positions:
                ok_positions.sort(key=lambda p: abs(p[0] - x) + abs(p[1] - y))
                x, y = ok_positions[0]
            for ix, c in enumerate(num_s):
                chars[int(round(x)) + ix][y] = "[1;97m" + c
        for corridor in self.corridors:
            if not corridor.name or not corridor.is_nontrivial(self):
                continue
            num_s = corridor.name
            x, y = corridor.middle_coords(self)
            x -= int(len(num_s) / 2.0)
            for dx, c in enumerate(num_s):
                chars[x + dx][y] = "[1;97m" + c
        if not colors:
            for x, l in enumerate(chars):
                for y, c in enumerate(l):
                    chars[x][y] = c[-1]
        return "\n".join(
            [
                "".join([chars[x][y] for x in range(self.width)])
                for y in range(self.height - 1, -1, -1)
            ]
        )


def is_room_valid(room, df, rooms, ix_to_ignore=None):
    if (
        room.x - room.rw < 1
        or room.y - room.rh < 1
        or room.x + room.rw >= df.width - 1
        or room.y + room.rh >= df.height - 1
    ):
        return False
    for ix, r2 in enumerate(rooms):
        if ix_to_ignore and ix == ix_to_ignore:
            continue
        if (abs(room.x - r2.x) <= room.rw + r2.rw + 1) and (
            abs(room.y - r2.y) <= room.rh + r2.rh + 1
        ):
            return False
    return True


def dfs(d, start, seen=None):
    seen = seen or set()
    seen.add(start)
    for other in d[start]:
        if other not in seen:
            dfs(d, other, seen)
    return seen


class DungeonConfig:
    def __init__(self):
        self.ui_ops = []
        self.var_keys = set()
        self.tk_types = {}
        self.tk_label_texts = {}
        self.tk_labels = {}
        self.tk_entries = {}
        self.tk_vars = {}
        self.tk_is_long = {}

        self.add_var("width", 35)
        self.add_var("height", 35)
        self.add_var("num_rooms", 12)
        self.add_var("min_room_radius", 1)
        self.add_var("num_room_embiggenings", 5)
        self.add_var("num_room_wiggles", 5)
        self.add_var("prefer_full_connection", True)
        self.add_var("min_corridors_per_room", 1.1)
        self.add_var("corridor_width_1_ratio", 1.0)
        self.add_var("corridor_width_2_ratio", 5.0)
        self.add_var("corridor_width_3_ratio", 2.0)
        self.add_var("num_up_ladders", 1)
        self.add_var("num_down_ladders", 1)
        self.add_var("tts_fog_of_war", False)
        self.add_var("tts_hidden_zones", True)
        self.ui_ops.append(("next group", None))
        self.add_var("target_character_level", 7)
        self.add_var("num_player_characters", 5)
        self.add_var("num_treasures", "2d4")
        self.add_var("num_mimics", "1d3-1")
        self.add_var("num_bookshelves", "1d4")
        self.add_var("room_encounter_percent", 70.0)
        self.add_var("encounter_xp_low_percent", 50.0)
        self.add_var("encounter_xp_high_percent", 200.0)
        self.add_var("monster_filter", "Undead or Flesh Golem", is_long=True)
        self.add_var("room_trap_percent", 30.0)
        self.add_var("corridor_trap_percent", 30.0)
        self.add_var("door_trap_percent", 15.0)
        self.add_var("chest_trap_percent", 30.0)
        self.allow_corridor_intersection = False
        self.min_ladder_distance = 2
        self.max_corridor_attempts = 20000
        self.max_room_attempts = 10000

    def add_var(self, k, v, tk_label=None, is_long=False):
        assert k not in self.var_keys
        assert type(v) in [int, float, str, bool]
        if not tk_label:
            tk_label = re.sub("num", "#", k)
            tk_label = re.sub("percent", "%", tk_label)
            tk_label = re.sub("_", " ", tk_label)
            tk_label = re.sub("tts", "TTS", tk_label)
            tk_label = " ".join(
                [x[0].upper() + x[1:] for x in tk_label.split(" ") if x]
            )
        self.var_keys.add(k)
        self.__dict__[k] = v
        self.tk_types[k] = type(v)
        self.tk_label_texts[k] = tk_label
        self.tk_is_long[k] = is_long
        self.ui_ops.append(("config", k))

    def make_tk_labels_and_entries(self, parent):
        row = 0
        group = 0
        for op, k in self.ui_ops:
            if op == "next group":
                group += 1
                row = 0
            if op != "config":
                continue
            if k in self.tk_labels:
                continue
            v = self.__dict__[k]
            self.tk_labels[k] = tk.Label(parent, text=self.tk_label_texts[k])
            var = None
            ty = self.tk_types[k]
            if ty == str:
                var = tk.StringVar()
            elif ty == int:
                var = tk.IntVar()
            elif ty == float:
                var = tk.DoubleVar()
            elif ty == bool:
                var = tk.BooleanVar()
            assert var
            var.set(v)
            self.tk_vars[k] = var
            if ty == bool:
                self.tk_entries[k] = tk.Checkbutton(parent, variable=var)
            else:
                if self.tk_is_long[k]:
                    self.tk_entries[k] = tk.Entry(
                        parent, textvariable=var, width=30
                    )
                else:
                    self.tk_entries[k] = tk.Entry(
                        parent, textvariable=var, width=5
                    )
            if self.tk_is_long[k]:
                self.tk_labels[k].grid(row=row, column=group * 2, columnspan=2)
                self.tk_entries[k].grid(
                    row=row + 1, column=group * 2, columnspan=2
                )
                row += 2
            else:
                self.tk_labels[k].grid(row=row, column=group * 2, sticky="e")
                self.tk_entries[k].grid(
                    row=row, column=group * 2 + 1, sticky="w"
                )
                row += 1

    def load_from_tk_entries(self):
        for k, var in self.tk_vars.items():
            self.__dict__[k] = var.get()


def generate_random_dungeon(config=None):
    config = config or DungeonConfig()
    df = DungeonFloor(config)
    place_rooms_in_dungeon(df, config)
    place_corridors_in_dungeon(df, config)
    place_doors_in_dungeon(df)
    place_ladders_in_dungeon(df)
    place_treasure_in_dungeon(df)
    place_monsters_in_dungeon(df)
    place_traps_in_dungeon(df)
    return df


def place_rooms_in_dungeon(df, config):
    # rooms
    rooms = []
    # generate some rooms in random locations
    for _ in range(config.max_room_attempts):
        if len(rooms) >= config.num_rooms:
            break
        room = df.random_room()
        if is_room_valid(room, df, rooms):
            rooms.append(room)
        elif len(rooms) > 0:
            # wiggle something a bit just in case this helps
            ix = random.randrange(0, len(rooms))
            room2 = rooms[ix].wiggled()
            if is_room_valid(room2, df, rooms, ix):
                rooms[ix] = room2

    # embiggen and wiggle rooms
    ews = ["e"] * config.num_room_embiggenings * config.num_rooms + [
        "w"
    ] * config.num_room_wiggles * config.num_rooms
    random.shuffle(ews)
    for op in ews:
        ix = random.randrange(0, len(rooms))
        room2 = None
        if op == "e":
            room2 = rooms[ix].embiggened()
        else:
            room2 = rooms[ix].wiggled()
        if is_room_valid(room2, df, rooms, ix):
            rooms[ix] = room2
    # sort rooms from top to bottom so their indices are more human comprehensible maybe
    rooms.sort(key=lambda r: (-r.y, r.x))
    # add rooms to dungeon floor
    for room in rooms:
        df.add_room(room)


def place_corridors_in_dungeon(df, config):
    rooms_connected = {}
    is_fully_connected = False
    for corridor_iteration in range(config.max_corridor_attempts):
        if (is_fully_connected or not config.prefer_full_connection) and len(
            df.corridors
        ) >= len(df.rooms) * config.min_corridors_per_room:
            break
        room1ix = random.randrange(len(df.rooms))
        room2ix = random.randrange(len(df.rooms))
        if room1ix == room2ix:
            continue
        room1ix, room2ix = sorted([room1ix, room2ix])
        if room2ix in (rooms_connected.get(room1ix) or set()):
            continue
        room1 = df.rooms[room1ix]
        room2 = df.rooms[room2ix]
        is_horizontal_first = random.randrange(2)
        width_prefs = [
            config.corridor_width_1_ratio,
            config.corridor_width_2_ratio,
            config.corridor_width_3_ratio,
        ]
        width_pref = random.random() * sum(width_prefs)
        width = 1
        for p in width_prefs:
            if width_pref <= p:
                break
            width_pref -= p
            width += 1

        corridor = Corridor(
            room1ix,
            room2ix,
            room1.x,
            room1.y,
            room2.x,
            room2.y,
            is_horizontal_first,
            width=width,
        )

        wall_entries = 0
        found_problem = False
        corridor_coords = list(corridor.walk())
        for ix in range(1, len(corridor_coords) - 1):
            x, y = corridor_coords[ix]
            px, py = corridor_coords[ix - 1]
            nx, ny = corridor_coords[ix + 1]
            if max(abs(px - x), abs(py - y), abs(nx - x), abs(ny - y)) > 1:
                # this is in between tunnel width iterations
                wall_entries = 0
                continue
            tile = df.tiles[x][y]
            ptile = df.tiles[px][py]
            ntile = df.tiles[nx][ny]
            if not config.allow_corridor_intersection and isinstance(
                tile, CorridorFloorTile
            ):
                found_problem = True
                break
            if not isinstance(tile, RoomFloorTile):
                if isinstance(ptile, RoomFloorTile):
                    wall_entries += 1
                    if wall_entries > 1:
                        found_problem = True
                        break
            if isinstance(tile, WallTile):
                pdx = x - px
                pdy = y - py
                ndx = nx - x
                ndy = ny - y
                reqd_walls = []
                if ndx == pdx and ndy == pdy:
                    # going the same direction, just ensure our sides are walls.
                    reqd_walls += [(x + ndy, y + ndx), (x - ndy, y - ndx)]
                else:
                    # we're in an elbow turn; ensure all are walls.
                    # if not (isinstance(ptile, CorridorFloorTile) and isinstance(ntile, CorridorFloorTile) and isinstance(tile, CorridorFloorTile)):
                    #    found_problem = True
                    #    break
                    # cl = [(x, y), (px, py), (nx, ny)]
                    for x2 in range(-1, 2):
                        for y2 in range(-1, 2):
                            reqd_walls.append((x + x2, y + y2))
                for x2, y2 in reqd_walls:
                    if not isinstance(df.tiles[x2][y2], WallTile):
                        found_problem = True
                        break
        if not found_problem:
            s = rooms_connected.get(room1ix) or set()
            s.add(room2ix)
            rooms_connected[room1ix] = s
            s = rooms_connected.get(room2ix) or set()
            s.add(room1ix)
            rooms_connected[room2ix] = s
            df.add_corridor(corridor)
            if not is_fully_connected and len(
                dfs(rooms_connected, room1ix)
            ) == len(df.rooms):
                is_fully_connected = True
    sorted_corridors = [
        (c, c.middle_coords(df)) for c in df.corridors if c.is_nontrivial(df)
    ]
    sorted_corridors.sort(key=lambda p: (-p[1][1], p[1][0]))
    for ix, p in enumerate(sorted_corridors):
        corridor = p[0]
        corridor.name = f"C{ix+1}"


def place_doors_in_dungeon(df):
    for corridor in df.corridors:
        corridor_coords = list(corridor.walk())
        for ix in range(1, len(corridor_coords) - 1):
            x, y = corridor_coords[ix]
            px, py = corridor_coords[ix - 1]
            nx, ny = corridor_coords[ix + 1]
            tile = df.tiles[x][y]
            ptile = df.tiles[px][py]
            ntile = df.tiles[nx][ny]
            if isinstance(ptile, RoomFloorTile) and isinstance(
                tile, CorridorFloorTile
            ):
                df.tiles[x][y] = DoorTile(tile.corridorix)
            elif (
                not isinstance(ptile, DoorTile)
                and isinstance(tile, CorridorFloorTile)
                and isinstance(ntile, RoomFloorTile)
            ):
                df.tiles[x][y] = DoorTile(tile.corridorix)
        for x, y in corridor.walk(max_width_iter=1):
            tile = df.tiles[x][y]
            if not isinstance(tile, DoorTile):
                continue
            door = Door(x, y, corridor.ix)
            df.add_door(door)
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    dtile = df.tiles[x + dx][y + dy]
                    if isinstance(dtile, DoorTile):
                        dtile.doorix = door.ix
                    elif isinstance(dtile, RoomFloorTile):
                        door.roomixs.add(dtile.roomix)
            corridor.doorixs.add(door.ix)
            for roomix in door.roomixs:
                df.rooms[roomix].doorixs.add(door.ix)


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
        output.append(next_layer)
    return output


def place_ladders_in_dungeon(df):
    num_up_ladders = 0
    num_down_ladders = 0
    # TODO: BFS check on ladders to be a configurable distance apart
    for _ in range(20000):
        if (
            num_up_ladders >= df.config.num_up_ladders
            and num_down_ladders >= df.config.num_down_ladders
        ):
            return
        roomix = random.randrange(len(df.rooms))
        room = df.rooms[roomix]
        if room.has_ladder():
            continue
        tile_coords = room.pick_tile(
            df, roomix, unoccupied=True, avoid_corridor=True, avoid_wall=True
        )
        if not tile_coords:
            continue
        x, y = tile_coords

        if num_up_ladders < df.config.num_up_ladders:
            df.tiles[x][y] = LadderUpTile(roomix)
            room.has_up_ladder = True
            num_up_ladders += 1
        else:
            df.tiles[x][y] = LadderDownTile(roomix)
            room.has_down_ladder = True
            num_down_ladders += 1


def place_treasure_in_dungeon(df):
    lib = get_treasure_library("dnd 5e treasure")
    monster_infos = get_monster_library("dnd 5e monsters").get_monster_infos()
    mimic_info = [i for i in monster_infos if i.name == "Mimic"][0]
    num_treasures = 0
    target_num_treasures = eval_dice(df.config.num_treasures)
    num_mimics = 0
    target_num_mimics = eval_dice(df.config.num_mimics)
    num_bookshelves = 0
    target_num_bookshelves = eval_dice(df.config.num_bookshelves)
    sized_roomixs = []
    for roomix, room in enumerate(df.rooms):
        for _ in range(room.total_space()):
            sized_roomixs.append(roomix)
    for _ in range(20000):
        if (
            num_treasures >= target_num_treasures
            and num_bookshelves >= target_num_bookshelves
            and num_mimics >= target_num_mimics
        ):
            return
        roomix = random.choice(sized_roomixs)
        room = df.rooms[roomix]
        if room.has_up_ladder:
            continue
        coords = room.pick_tile(
            df, roomix, unoccupied=True, avoid_corridor=True, prefer_wall=True
        )
        if not coords:
            continue
        x, y = coords

        if num_treasures < target_num_treasures:
            contents = lib.gen_horde(
                df.config.target_character_level,
                df.config.num_player_characters,
            )
            if not contents:
                contents = ["Nothing!"]
            df.tiles[x][y] = ChestTile(roomix, contents="\n".join(contents))
            num_treasures += 1
        elif num_bookshelves < target_num_bookshelves:
            contents = lib.gen_bookshelf_horde(
                df.config.target_character_level,
                df.config.num_player_characters,
            )
            if not contents:
                contents = ["Nothing!"]
            df.tiles[x][y] = BookshelfTile(roomix, contents="\n".join(contents))
            num_bookshelves += 1
        else:
            monster = Monster(mimic_info)
            monster.adjust_cr(df.config.target_character_level)
            df.tiles[x][y] = MimicTile(roomix, monster=monster)
            num_mimics += 1


class Encounter:
    def __init__(self, monsters=None):
        self.monsters = monsters or []

    def total_xp(self):
        tmp_sum = sum([m.monster_info.xp for m in self.monsters])
        # sqrt approximates the table from the DMG for modifying
        # difficulty with multiple monsters. This does not yet ignore
        # monsters with substantially lowered CR.
        return int(tmp_sum * math.sqrt(len(self.monsters)))

    def total_space(self):
        return sum([m.monster_info.diameter**2 for m in self.monsters])

    def description(self):
        return summarize_monsters(self.monsters)


def summarize_monsters(monsters):
    monster_counts = collections.defaultdict(int)
    infos = {}
    for monster in monsters:
        infos[monster.monster_info.name] = monster.monster_info
        monster_counts[monster.monster_info.name] += 1
    o = []
    for k in sorted(monster_counts.keys()):
        o.append(f"{k} ({infos[k].ascii_char}) x{monster_counts[k]}")
    return "\n".join(o)


def _build_encounter_single_attempt(
    monster_infos, target_xp, variety, prev_monster_counts={}
):
    # TODO: there is some bug, I think, where it's not willing to
    # generate a Banshee (homogenous, max 1 per floor)
    used_infos = {}  # name -> info
    encounter = Encounter()
    prev_xp = -1000000
    eligible_monsters = []
    monster_counts = collections.defaultdict(int)
    for _ in range(100):
        if len(encounter.monsters) >= variety or len(used_infos) >= len(
            monster_infos
        ):
            break
        mi = random.choice(monster_infos)
        if mi.name in used_infos:
            continue
        used_infos[mi.name] = mi
        if mi.frequency <= 0.0:
            continue
        if variety != 1 and mi.has_keyword("Homogenous"):
            continue
        if mi.max_per_floor is not None:
            if prev_monster_counts[mi.name] >= mi.max_per_floor:
                continue
        encounter.monsters.append(Monster(mi))
        new_xp = encounter.total_xp()
        if abs(target_xp - new_xp) < abs(target_xp - prev_xp):
            eligible_monsters.append(mi.name)
            prev_xp = new_xp
            monster_counts[mi.name] += 1
        else:
            encounter.monsters.pop()
    for _ in range(100):
        if not eligible_monsters:
            break
        name = random.choice(eligible_monsters)
        mi = used_infos[name]
        encounter.monsters.append(Monster(mi))
        new_xp = encounter.total_xp()
        if abs(target_xp - new_xp) < abs(target_xp - prev_xp):
            prev_xp = new_xp
            monster_counts[name] += 1
            if mi.max_per_floor is not None:
                if (
                    prev_monster_counts[name] + monster_counts[name]
                    >= mi.max_per_floor
                ):
                    eligible_monsters = list(
                        set(eligible_monsters) - set([name])
                    )
        else:
            encounter.monsters.pop()
            eligible_monsters = list(set(eligible_monsters) - set([name]))
    return encounter


def score_encounter(encounter, target_xp, prev_monster_counts):
    xp = encounter.total_xp()
    score = 1.0 - abs(xp - target_xp) / target_xp
    monster_infos = {}  # name -> info
    monster_counts = collections.defaultdict(int)
    for m in encounter.monsters:
        monster_infos[m.monster_info.name] = m.monster_info
        monster_counts[m.monster_info.name] += 1
    # get a poor score if it's all frontline or all backline.
    all_backline = True
    all_frontline = True
    for mi in monster_infos.values():
        if not mi.has_keyword("Backline"):
            all_backline = False
        if not mi.has_keyword("Frontline"):
            all_frontline = False
    if all_backline or all_frontline:
        score /= 2.0
    # improve or worsen score if you have or don't have synergistic
    # buddies.
    has_synergies = set()
    found_synergies = set()
    for mi in monster_infos.values():
        if mi.synergies:
            has_synergies.add(mi.name)
            for s in mi.synergies:
                if s in monster_infos:
                    found_synergies.add(mi.name)
    if len(has_synergies) > len(found_synergies):
        score /= 2.0
    else:
        score *= 1.0 + len(has_synergies)
    # frequency bonuses?
    new_things = set()
    for name, mi in monster_infos.items():
        if name not in prev_monster_counts:
            new_things.add(name)
        if mi.max_per_floor is not None:
            if (
                monster_counts[name] + prev_monster_counts[name]
                > mi.max_per_floor
            ):
                score /= 10.0
    score *= 1.0 + len(new_things)
    return score


def build_encounter(
    monster_infos, target_xp, variety=None, prev_monster_counts={}
):
    if not variety:
        varieties = [1, 2, 2, 3, 3, 3, 4, 4]
        variety = random.choice(varieties)
    monster_infos = [
        mi for mi in monster_infos if mi.xp and mi.xp <= target_xp * 1.3
    ]
    variety = min(variety, len(monster_infos))
    best_encounter = Encounter()
    best_score = 0.0001
    for _ in range(100):
        encounter = _build_encounter_single_attempt(
            monster_infos, target_xp, variety, prev_monster_counts
        )
        score = score_encounter(encounter, target_xp, prev_monster_counts)
        if score > best_score:
            best_encounter = encounter
            best_score = score
    return best_encounter


def med_target_xp(config):
    med_xp_per_char = {
        1: 50,
        2: 100,
        3: 150,
        4: 250,
        5: 500,
        6: 600,
        7: 750,
        8: 900,
        9: 1100,
        10: 1200,
        11: 1600,
        12: 2000,
        13: 2200,
        14: 2500,
        15: 2800,
        16: 3200,
        17: 3900,
        18: 4200,
        19: 4900,
        20: 5700,
    }[config.target_character_level]
    return med_xp_per_char * config.num_player_characters


def place_monsters_in_dungeon(df):
    config = df.config
    max_cr = int(math.ceil(config.target_character_level * 7.0 / 5.0))
    monster_infos = get_monster_library("dnd 5e monsters").get_monster_infos(
        filter=config.monster_filter,
        max_challenge_rating=max_cr,
        has_tts=True,
    )
    if not monster_infos:
        return  # no monsters matched whatever filters
    lowest_monster_xp = min((m.xp for m in monster_infos if m.xp))
    num_monster_encounters = 0
    target_monster_encounters = round(
        len(df.rooms) * config.room_encounter_percent / 100.0
    )
    roomixs = []
    for roomix in range(len(df.rooms)):
        if df.rooms[roomix].has_ladder():  # no monsters in ladder rooms
            continue
        roomixs.append(roomix)
    random.shuffle(roomixs)
    roomixs = roomixs[:target_monster_encounters]
    roomixs.sort(key=lambda ix: df.rooms[ix].total_space())
    encounters = []
    monster_counts = collections.defaultdict(int)
    for _ in roomixs:
        lo = config.encounter_xp_low_percent
        hi = config.encounter_xp_high_percent
        xp_percent_of_medium = lo + random.random() * abs(hi - lo)
        target_xp = max(
            round(med_target_xp(config) * xp_percent_of_medium * 0.01),
            lowest_monster_xp,
        )
        enc = build_encounter(
            monster_infos, target_xp, prev_monster_counts=monster_counts
        )
        if not enc.monsters:
            continue
        for m in enc.monsters:
            monster_counts[m.monster_info.name] += 1
        encounters.append(enc)
    encounters.sort(key=lambda e: e.total_space())

    for roomix, encounter in zip(roomixs, encounters):
        room = df.rooms[roomix]
        room.encounter = encounter
        monsters = list(encounter.monsters)
        random.shuffle(monsters)
        monsters.sort(key=lambda m: -m.monster_info.xp)
        for monster in monsters:
            tile_coords = room.pick_tile(
                df,
                roomix,
                unoccupied=True,
                diameter=monster.monster_info.diameter,
            )
            if not tile_coords:
                continue
            monster.x, monster.y = tile_coords
            monster.roomix = roomix
            df.add_monster(monster)
        num_monster_encounters += 1


def place_traps_in_dungeon(df):
    level = df.config.target_character_level
    config = df.config
    roomixs_to_trap = []
    target_num_room_traps = int(
        len(df.rooms) * config.room_trap_percent / 100.0
    )
    for roomix, room in enumerate(df.rooms):
        if room.has_ladder():
            continue
        roomixs_to_trap.append(roomix)
    random.shuffle(roomixs_to_trap)
    for roomix in roomixs_to_trap[:target_num_room_traps]:
        trap = RoomTrap.create(config, roomix)
        df.add_trap(trap)
        df.rooms[roomix].trapixs.add(trap.ix)

    corridorixs_to_trap = []
    for corridorix, corridor in enumerate(df.corridors):
        if corridor.is_nontrivial(df):
            corridorixs_to_trap.append(corridorix)
    target_num_corridor_traps = int(
        len(corridorixs_to_trap) * config.corridor_trap_percent / 100.0
    )
    random.shuffle(corridorixs_to_trap)
    corridorixs_to_trap = corridorixs_to_trap[:target_num_corridor_traps]
    for corridorix in corridorixs_to_trap:
        trap = CorridorTrap.create(config, corridorix)
        df.add_trap(trap)
        df.corridors[corridorix].trapixs.add(trap.ix)
    doors_to_trap = list(df.doors)
    target_num_door_traps = int(
        len(doors_to_trap) * config.door_trap_percent / 100.0
    )
    random.shuffle(doors_to_trap)
    num_door_traps = 0
    for door in doors_to_trap:
        if door.corridorix in corridorixs_to_trap:
            continue
        if num_door_traps >= target_num_door_traps:
            break
        num_door_traps += 1
        trap = DoorTrap.create(config, door.ix, door.x, door.y)
        df.add_trap(trap)
        door.trapixs.add(trap.ix)

    # chests
    chest_coords = []
    for x in range(df.width):
        for y in range(df.height):
            tile = df.tiles[x][y]
            if tile.is_chest():
                chest_coords.append((x, y))
    target_num_chest_traps = int(
        len(chest_coords) * config.chest_trap_percent / 100.0
    )
    random.shuffle(chest_coords)
    for x, y in chest_coords[:target_num_chest_traps]:
        trap = ChestTrap.create(config, x, y)
        df.add_trap(trap)
        df.tiles[x][y].trapixs.add(trap.ix)


def dungeon_to_tts_blob(df):
    name = f"Caverns of Carl {datetime.datetime.now():%Y-%m-%dT%H-%M-%S%z}"
    blob = copy.deepcopy(tts_reference_save_json())
    blob["SaveName"] = name
    blob["GameMode"] = name
    blob["ObjectStates"] = []
    for x in range(df.width):
        for y in range(df.height):
            tile = df.tiles[x][y]
            obj = tile.tts_object(df, x, y)
            if obj is None:
                continue
            df.tts_xz(x, y, obj)
            blob["ObjectStates"].append(obj)
    for monster in df.monsters:
        obj = monster.tts_object(df)
        blob["ObjectStates"].append(obj)
    for roomix, room in enumerate(df.rooms):
        blob["ObjectStates"].append(room.tts_notecard(df))
    for corridorix, corridor in enumerate(df.corridors):
        if corridor.is_nontrivial(df):
            blob["ObjectStates"].append(corridor.tts_notecard(df))
    for trap in df.traps:
        if isinstance(trap, RoomTrap) or isinstance(trap, CorridorTrap):
            continue
        obj = tts_reference_object("Reference Notecard")
        desc = trap.description()
        obj["Nickname"] = desc.split("\n")[0]
        obj["Description"] = "\n".join(desc.split("\n")[1:])
        obj["Transform"]["posY"] = 4.0
        obj["Locked"] = True
        df.tts_xz(trap.x, trap.y, obj)
        blob["ObjectStates"].append(obj)
    if df.config.tts_fog_of_war:
        fog = tts_fog(scaleX=df.width + 2.0, scaleZ=df.height + 2.0)
        blob["ObjectStates"].append(fog)
    if df.config.tts_hidden_zones:
        fog_bits = {}  # TTSFogBit.coord_tuple():TTSFogBit
        tmp_fog_bit_list = []
        for roomix, room in enumerate(df.rooms):
            for bit in room.tts_fog_bits(roomix):
                tmp_fog_bit_list.append(bit)
        for corridorix, corridor in enumerate(df.corridors):
            for bit in corridor.tts_fog_bits(df, corridorix):
                tmp_fog_bit_list.append(bit)
        for x in range(df.width):
            for y in range(df.height):
                tmp_fog_bit_list.append(TTSFogBit(x, y))
        for bit in tmp_fog_bit_list:
            coords = bit.coord_tuple()
            other_bit = fog_bits.get(coords)
            if other_bit:
                bit.merge_from_other(other_bit)
            fog_bits[coords] = bit
        merged_bits = TTSFogBit.merge_fog_bits(fog_bits.values())
        for bit in merged_bits:
            blob["ObjectStates"].append(bit.tts_fog(df))
    # DM's (hopefully) helpful hidden zone
    dm_fog = tts_fog(scaleX=df.width, scaleZ=20.0, hidden_zone=True)
    df.tts_xz(df.width / 2.0 - 0.5, -10.5, dm_fog)
    blob["ObjectStates"].append(dm_fog)
    # Add tags for easy mass deletion.
    for o1 in blob["ObjectStates"]:
        for o in [o1] + list(o1.get("States", {}).values()):
            tags = set(o.get("Tags", []))
            tags.add(_TTS_SPAWNED_TAG)
            tags.add(f"{_TTS_SPAWNED_TAG} '{name}'")
            o["Tags"] = list(tags)
    return blob


def save_tts_blob(blob):
    filename = os.path.join(
        tts_default_save_location(), blob["SaveName"] + ".json"
    )
    with open(filename, "w") as f:
        json.dump(blob, f, indent=2)
    return filename


def set_tk_text(tk_text, s, default_tag_kwargs={}, style_newlines=False):
    tk_text.delete("1.0", tk.END)
    for tag in tk_text.tag_names():
        tk_text.tag_delete(tag)
    font_info = tkinter.font.nametofont(tk_text.cget("font")).actual()
    bold_font_info = dict(font_info)
    bold_font_info["weight"] = "bold"
    bold_font = tkinter.font.Font(**bold_font_info)
    underline_font_info = dict(font_info)
    underline_font_info["underline"] = True
    underline_font = tkinter.font.Font(**bold_font_info)
    tag_db = {}
    if default_tag_kwargs:
        tk_text.tag_configure("defaultish", **default_tag_kwargs)
        tag_db[(-1, -1)] = "defaultish"
    lines = s.split("\n")
    for lineix, line in enumerate(lines):
        ix = 0
        colored_chars = []
        while ix < len(line):
            if ix + 6 < len(line):
                possible_code = line[ix : ix + 6]
                if re.match(r"^\[[0-9];[0-9][0-9]m$", possible_code):
                    style = int(possible_code[1])
                    color = int(possible_code[3:5])
                    colored_chars.append((line[ix + 6], style, color))
                    ix += 7
                    continue
            colored_chars.append((line[ix], None, None))
            ix += 1
        for ix, tup in enumerate(colored_chars):
            c, style, color = tup
            tk_text.insert(tk.END, c)
            if style is None or color is None:
                if not default_tag_kwargs:
                    continue
                style, color = -1, -1
            tag_name = None
            if (style, color) not in tag_db:
                tag_name = f"s{style}c{color}"
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
                }[color]
                d = dict(default_tag_kwargs or {})
                d["foreground"] = color_hex
                d["background"] = "#000"
                if style == 1:
                    d["font"] = bold_font
                if style == 4:
                    d["font"] = underline_font
                tk_text.tag_configure(tag_name, **d)
                tag_db[(style, color)] = tag_name
            tag_name = tag_db[(style, color)]
            tk_text.tag_add(tag_name, f"{lineix+1}.{ix}", f"{lineix+1}.{ix+1}")

        if lineix < len(lines) - 1:
            tk_text.insert(tk.END, "\n")
            if style_newlines:
                tk_text.tag_add(tag_name, f"{lineix+1}.{ix}", tk.END)
    pass


def run_ui():
    config = DungeonConfig()
    dungeon_history = []

    root = tk.Tk()
    root.title("Caverns of Carl")
    root.columnconfigure(0, weight=1)
    root.columnconfigure(1, weight=1)
    root.columnconfigure(2, weight=1)
    root.rowconfigure(0, weight=1)
    left_frame = tk.Frame(root, borderwidth=2, relief="groove")
    middle_frame = tk.Frame(root, borderwidth=2, relief="groove")
    right_frame = tk.Frame(root, borderwidth=2, relief="groove")
    left_frame.grid(row=0, column=0, sticky="nsew")
    middle_frame.grid(row=0, column=1, sticky="nsew")
    right_frame.grid(row=0, column=2, sticky="nsew")

    # Configuration Frame
    config_label = tk.Label(left_frame, text="Configuration", width=70)
    config_label.pack()

    # dungeon dimensions
    size_frame = tk.Frame(left_frame)
    config.make_tk_labels_and_entries(size_frame)
    size_frame.pack()

    def new_preview(*args, **kwargs):
        set_tk_text(ascii_map_text, "")
        set_tk_text(chest_info_text, "")

        text_output = []
        err = None
        try:
            config.load_from_tk_entries()
            df = generate_random_dungeon(config)
            dungeon_history.append(df)

            text_output.append("Floor monster counts:")
            text_output.append(summarize_monsters(df.monsters))
            text_output.append("")
            for room in df.rooms:
                text_output.append(f"***Room {room.ix}***")
                text_output.append(room.description(df, verbose=True))
                text_output.append("")
            for corridor in df.corridors:
                if not corridor.is_nontrivial(df):
                    continue
                text_output.append(f"***Corridor {corridor.name}***")
                text_output.append(corridor.description(df, verbose=True))
                text_output.append("")
        except Exception as e:
            err = traceback.format_exc()
        if err:
            text_output = [err]
        else:
            ascii = dungeon_history[-1].ascii(colors=True)
            set_tk_text(
                ascii_map_text,
                ascii,
                {"foreground": "#fff", "background": "#000"},
            )
        set_tk_text(
            chest_info_text,
            "\n".join(text_output),
            {"foreground": "#fff", "background": "#000"},
        )

    def save_dungeon(*args, **kwargs):
        if not dungeon_history:
            return
        text_output = ""
        try:
            df = dungeon_history[-1]
            fn = save_tts_blob(dungeon_to_tts_blob(df))
            text_output = f"Saved to {fn}"
        except Exception as e:
            text_output = traceback.format_exc()
        chest_info_text.insert(tk.END, f"\n\n{text_output}")
        chest_info_text.see(tk.END)

    operation_frame = tk.Frame(left_frame)
    generate_button = tk.Button(
        operation_frame, text="Generate", command=new_preview
    )
    generate_button.grid(row=0, column=0)
    save_button = tk.Button(
        operation_frame, text="Save to TTS", command=save_dungeon
    )
    save_button.grid(row=0, column=1)
    operation_frame.pack(pady=10)

    ascii_map_label = tk.Label(middle_frame, text="ASCII Map")
    ascii_map_label.pack(pady=10)
    ascii_map_text = scrolledtext.ScrolledText(
        middle_frame,
        wrap=tk.NONE,
        width=57,
        height=35,
        foreground="#fff",
        background="#000",
    )
    # Create a horizontal scrollbar and attach it to the ScrolledText widget
    hscrollbar = tk.Scrollbar(
        middle_frame, orient="horizontal", command=ascii_map_text.xview
    )
    ascii_map_text["xscrollcommand"] = hscrollbar.set
    # Pack the horizontal scrollbar
    hscrollbar.pack(side=tk.BOTTOM, fill=tk.X)
    ascii_map_text.pack(expand=True, fill="both")

    chest_info_label = tk.Label(right_frame, text="Logs and Information")
    chest_info_label.pack(pady=10)

    chest_info_text = scrolledtext.ScrolledText(
        right_frame, foreground="#fff", background="#000"
    )
    chest_info_text.pack(expand=True, fill="both", padx=10, pady=10)

    new_preview()

    root.state("zoomed")
    root.mainloop()


if __name__ == "__main__":
    run_ui()
    exit()
    dungeon = generate_random_dungeon()
    print(dungeon.ascii())
    for x in range(dungeon.width):
        for y in range(dungeon.height):
            tile = dungeon.tiles[x][y]
            if False and isinstance(tile, BookshelfTile) and tile.contents:
                print("\nContents:")
                print(tile.contents)

    monster_counts = collections.defaultdict(int)
    for m in dungeon.monsters:
        monster_counts[m.monster_info.name] += 1
    # print(sorted(monster_counts.items()))
    for trap in dungeon.traps:
        # print(type(trap).__name__, trap.trigger, trap.effect)
        pass
    save_tts_blob(dungeon_to_tts_blob(dungeon))
