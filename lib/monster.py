import copy
import json
import os
import random
import re

import lib.tts as tts
from lib.utils import COC_ROOT_DIR, expr_match_keywords, eval_dice


_monster_library_cache = {}


def get_monster_library(name):
    if name not in _monster_library_cache:
        ml = MonsterLibrary(name=name)
        ml.load()
        _monster_library_cache[name] = ml
    return _monster_library_cache[name]


class MonsterLibrary:
    def __init__(self, name):
        self.name = name
        self.monster_infos = []

    def load(self):
        filename = os.path.join(
            COC_ROOT_DIR, "reference_info", "monsters", f"{self.name}.json"
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
            COC_ROOT_DIR, "reference_info", "monsters", f"{self.name}.json"
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
        obj = tts.reference_object(ref_nick)
        df.tts_xz(self.x, self.y, obj, diameter=self.monster_info.diameter)
        obj["Transform"]["posY"] = 2.0
        # TODO: adjust to not face wall if near wall?
        obj["Transform"]["rotY"] = 90.0 * random.randrange(4)
        obj["Nickname"] = self.tts_nickname()
        return obj
