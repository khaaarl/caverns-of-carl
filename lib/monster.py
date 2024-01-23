import collections
import copy
import functools
import json
import math
import os
import random
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if _ROOT not in sys.path:
    sys.path.append(_ROOT)

import lib.tts as tts
from lib.utils import (
    COC_ROOT_DIR,
    Doc,
    choice,
    expr_match_keywords,
    eval_dice,
    remove_non_ascii,
)


@functools.cache
def get_monster_library(name):
    ml = MonsterLibrary(name=name)
    ml.load()
    return ml


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
        infos = sorted(
            self.monster_infos, key=lambda x: (x.challenge_rating or 0, x.name)
        )
        return {
            "name": self.name,
            "monsters": [x.to_blob() for x in infos],
        }

    def save(self):
        filename = os.path.join(
            COC_ROOT_DIR, "reference_info", "monsters", f"{self.name}.json"
        )
        with open(filename, "w") as f:
            json.dump(self.to_blob(), f, sort_keys=True, indent=2)

    def get_monster_infos(
        self,
        filter=None,
        min_challenge_rating=None,
        max_challenge_rating=None,
        has_tts=False,
    ):
        output = []
        for m in self.monster_infos:
            if has_tts and not (
                m.tts_reference_nicknames or tts.has_reference_object(m.name)
            ):
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

    def ingest_5e_tools_json(self, filename):
        infos = collections.defaultdict(MonsterInfo)
        for mi in self.monster_infos:
            infos[mi.name] = mi
        others = []
        with open(filename) as f:
            blob = json.load(f)
            others = blob["monster"]
        for m in others:
            if "hp" not in m:
                continue
            name = remove_non_ascii(m["name"])
            mi = infos[name]
            mi.name = name
            mi.health = m["hp"]["average"]
            mi.hit_dice_formula = m["hp"]["formula"]
            mi.size = {
                "T": "tiny",
                "S": "small",
                "M": "medium",
                "L": "large",
                "H": "huge",
                "G": "gargantuan",
            }[m.get("size", ["M"])[0]]
            cr = None
            if "cr" in m:
                tmp = m["cr"]
                if isinstance(tmp, dict):
                    tmp = tmp.get("cr")
                if tmp == "1/2":
                    cr = 0.5
                elif tmp == "1/4":
                    cr = 0.25
                elif tmp == "1/8":
                    cr = 0.125
                elif tmp and tmp.isdigit():
                    cr = int(tmp)
            if cr is not None:
                mi.challenge_rating = cr
            # keywords
            keywords = set(mi.keywords)
            if "spellcasting" in m:
                keywords.add("Spellcaster")
            if "type" in m:
                tmp = m["type"]
                if isinstance(tmp, dict):
                    keywords.add(tmp["type"])
                    for tag in tmp.get("tags", []):
                        if tag.lower() == "orc":
                            tag = "orcoid"
                        keywords.add(tag)
                elif isinstance(tmp, str):
                    keywords.add(tmp)
            for sense in m.get("senses", []):
                keywords.add(sense.split()[0])
            for environment in m.get("environment", []):
                keywords.add(environment)
            for k in m.get("speed", {}).keys():
                if k == "burrow":
                    keywords.add("Burrowing")
                if k == "climb":
                    keywords.add("Climbing")
                if k == "fly":
                    keywords.add("Flying")
                if k == "swim":
                    keywords.add("Swimming")
            mi.keywords = sorted({a.title() for a in keywords})
        self.monster_infos = infos.values()


_CR_TO_HP_RATIO = {
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
_CR_TO_XP = {
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


class MonsterInfo:
    _KEYS_DEFAULTS = {
        "name": "Unnamed Monster",
        "keywords": [],
        "tts_reference_nicknames": [],
        "ascii_char": "e",
        "health": None,
        "hit_dice_formula": None,
        "size": "medium",
        "synergies": [],
        "challenge_rating": None,
        "max_per_floor": None,
        "frequency": 1.0,
    }

    def __init__(self, blob={}):
        for k, default in MonsterInfo._KEYS_DEFAULTS.items():
            self.__dict__[k] = blob.get(k, default)
        self.diameter = {
            "tiny": 1,
            "small": 1,
            "medium": 1,
            "large": 2,
            "huge": 3,
            "gargantuan": 3,
        }[self.size]
        self.xp = None
        if self.challenge_rating is not None:
            self.xp = _CR_TO_XP[self.challenge_rating]

    def to_blob(self):
        blob = {}
        for k, default in MonsterInfo._KEYS_DEFAULTS.items():
            v = self.__dict__[k]
            if v != default:
                blob[k] = v
        return blob

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
        old_cr = self.monster_info.challenge_rating
        if new_cr == old_cr:
            return
        self.monster_info = copy.deepcopy(self.monster_info)
        self.monster_info.challenge_rating = new_cr
        self.monster_info.xp = _CR_TO_XP[new_cr]
        if self.health:
            rat = _CR_TO_HP_RATIO[new_cr] / _CR_TO_HP_RATIO[old_cr]
            self.health = max(1, round(self.health * rat))
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
        ref_nick = self.monster_info.name
        if self.monster_info.tts_reference_nicknames:
            ref_nick = random.choice(self.monster_info.tts_reference_nicknames)
        obj = tts.reference_object(ref_nick)
        df.tts_xz(self.x, self.y, obj, diameter=self.monster_info.diameter)
        obj["Transform"]["posY"] = 2.0
        if obj["Name"] == "Figurine_Custom":
            obj["Transform"]["posY"] = 2.06
        # TODO: adjust to not face wall if near wall?
        obj["Transform"]["rotY"] = 90.0 * random.randrange(4)
        obj["Nickname"] = self.tts_nickname()
        obj["Locked"] = False
        return obj


class Encounter:
    def __init__(self, monsters=None):
        self.monsters = monsters or []

    def total_xp(self):
        tmp_sum = sum([m.monster_info.xp for m in self.monsters])
        # Count up the monsters, but monsters significantly lower CR
        # don't count as much. I'm attenuating by the square root of
        # the difference in CR minus 1, so 2 CR difference doesn't
        # change things, but going lower than that counds for a good
        # deal less.
        hi_cr = max([m.monster_info.challenge_rating for m in self.monsters])
        count = 0.0
        for m in self.monsters:
            dcount = 1.0
            if m.monster_info.challenge_rating < hi_cr - 2:
                dcount /= math.sqrt(hi_cr - 1 - m.monster_info.challenge_rating)
            count += dcount
        # sqrt approximates the table from the DMG for modifying
        # difficulty with multiple monsters. This does not yet ignore
        # monsters with substantially lowered CR.
        return int(tmp_sum * math.sqrt(count))

    def total_space(self):
        return sum([m.monster_info.diameter**2 for m in self.monsters])

    def description(self, df):
        xp = self.total_xp()
        pct = int(round(100.0 * xp / med_target_xp(df.config)))
        header = f"Monster encounter (~{xp:,} xp; ~{pct}% of Medium):"
        return Doc(header, summarize_monsters(self.monsters))


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
    monster_infos, target_xp, variety, prev_monster_counts={}, max_space=None
):
    used_infos = {}  # name -> info
    encounter = Encounter()
    prev_xp = -1000000
    eligible_monsters = []
    eligible_monster_freqs = []
    monster_counts = collections.defaultdict(int)
    monster_infos = [m for m in monster_infos if m.frequency > 0.0]
    removable_monster_infos = list(monster_infos)
    monster_freqs = [m.frequency for m in monster_infos]
    for _ in range(100):
        if len(encounter.monsters) >= variety or len(used_infos) >= len(
            monster_infos
        ):
            break
        ix, mi = choice(list(enumerate(removable_monster_infos)), monster_freqs)
        used_infos[mi.name] = mi
        del removable_monster_infos[ix]
        del monster_freqs[ix]
        if variety != 1 and mi.has_keyword("Homogenous"):
            continue
        if mi.max_per_floor is not None:
            if prev_monster_counts[mi.name] >= mi.max_per_floor:
                continue
        if max_space is not None:
            if encounter.total_space() + mi.diameter**2 > max_space:
                continue
        encounter.monsters.append(Monster(mi))
        new_xp = encounter.total_xp()
        if abs(target_xp - new_xp) < abs(target_xp - prev_xp):
            eligible_monsters.append(mi.name)
            eligible_monster_freqs.append(mi.frequency)
            prev_xp = new_xp
            monster_counts[mi.name] += 1
        else:
            encounter.monsters.pop()
    for _ in range(100):
        if not eligible_monsters:
            break
        ix, name = choice(
            list(enumerate(eligible_monsters)), eligible_monster_freqs
        )
        mi = used_infos[name]
        encounter.monsters.append(Monster(mi))
        new_xp = encounter.total_xp()
        is_improved = abs(target_xp - new_xp) < abs(target_xp - prev_xp)
        if max_space is not None:
            if encounter.total_space() > max_space:
                is_improved = False
        if mi.max_per_floor is not None:
            new_count = prev_monster_counts[name] + monster_counts[name] + 1
            if new_count > mi.max_per_floor:
                is_improved = False
        if is_improved:
            prev_xp = new_xp
            monster_counts[name] += 1
        else:
            encounter.monsters.pop()
            del eligible_monsters[ix]
            del eligible_monster_freqs[ix]
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
    monster_infos,
    target_xp,
    variety=None,
    prev_monster_counts={},
    max_space=None,
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
            monster_infos, target_xp, variety, prev_monster_counts, max_space
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


if __name__ == "__main__":
    ml = get_monster_library("dnd 5e monsters")
    # ml.ingest_5e_tools_json(r"C:\Users\carl\Downloads\bestiary-vgm.json")
    ml.save()
