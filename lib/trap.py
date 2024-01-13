import collections
import copy
import datetime
import json
import math
import os
import random
import re
import traceback

from lib.utils import bfs, choice, dfs, expr_match_keywords, eval_dice, samples


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
    "Falling rocks: Dex {DC} for half, {DAM:bludgeoning}",
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
_ENCLOSED_DOORS_TRAP_EFFECTS = [
    "Doors shut and lock: Str(Ath) or Arcana or Thieves' Tools {DC}. {SLOW_DAMAGE_TRAP_EFFECT}",
    "Doors shut and lock: Str(Ath) or Arcana or Thieves' Tools {DC}. Repeated Con {DC-2}; fail 3 and get infected with {DISEASE}",
]
_MISC_CORRIDOR_TRAP_EFFECTS = [
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
    def create(config, room):
        trap = RoomTrap(config, room.ix)
        tgs = _AREA_TRAP_TRIGGERS
        trap.trigger = random.choice(tgs)
        effs = (
            _ONE_OFF_DAMAGE_TRAP_EFFECTS
            + _SLOW_DAMAGE_TRAP_EFFECTS
            + _MISC_TRAP_EFFECTS
            + _MISC_ROOM_OR_CORRIDOR_TRAP_EFFECTS
        )
        if room.is_fully_enclosed_by_doors():
            effs += _ENCLOSED_DOORS_TRAP_EFFECTS
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
    def create(config, corridor):
        trap = CorridorTrap(config, corridor.ix)
        tgs = _AREA_TRAP_TRIGGERS + _CORRIDOR_TRAP_TRIGGERS
        trap.trigger = random.choice(tgs)
        effs = (
            _ONE_OFF_DAMAGE_TRAP_EFFECTS
            + _MISC_TRAP_EFFECTS
            + _MISC_ROOM_OR_CORRIDOR_TRAP_EFFECTS
        )
        if corridor.is_fully_enclosed_by_doors():
            effs += _ENCLOSED_DOORS_TRAP_EFFECTS
        if corridor.doorixs:
            effs += _MISC_CORRIDOR_TRAP_EFFECTS
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
