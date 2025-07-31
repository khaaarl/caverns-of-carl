import functools
import json
import math
import os

import lib.tts as tts
from lib.utils import COC_ROOT_DIR, Doc


@functools.cache
def npc_library():
    filename = os.path.join(
        COC_ROOT_DIR, "reference_info", "npcs", "npcs.json"
    )
    npcs = {}
    with open(filename) as f:
        blob = json.load(f)
        for npc_blob in blob["npcs"]:
            npc = Npc(npc_blob)
            if npc.name:
                npcs[npc.name] = npc
    return npcs


class Npc:
    def __init__(self, blob):
        self.x = None
        self.y = None
        self.rotation = 0.0
        self.roomix = None

        self.name = blob.get("Name", "")
        self.race = blob.get("Race", "")
        self.character_class = blob.get("Class", "")
        self.level = int(blob.get("Level", "0")) or None
        self.health = int(blob.get("Hit Points", "0")) or None
        self.armor_class = int(blob.get("Armor Class", "0")) or None

        self.strength = int(blob.get("Strength", "0")) or None
        self.constitution = int(blob.get("Constitution", "0")) or None
        self.dexterity = int(blob.get("Dexterity", "0")) or None
        self.intelligence = int(blob.get("Intelligence", "0")) or None
        self.wisdom = int(blob.get("Wisdom", "0")) or None
        self.charisma = int(blob.get("Charisma", "0")) or None

        self.skills = blob.get("Skills", [])
        self.abilities = blob.get("Abilities", [])
        self.spells = blob.get("Spells", [])
        self.attacks = blob.get("Attacks", [])

        self.appearance = blob.get("Appearance", "")
        self.voice = blob.get("Voice", "")
        self.personality = blob.get("Personality", "")
        self.quirks = blob.get("Quirks", [])
        self.motivation = blob.get("Motivation", "")
        self.activities = blob.get("Activities", [])

        self.tts_reference_nickname = blob.get("TTS Reference Nickname", "")

    def tts_object(self, df, x=None, y=None):
        ref_nick = self.tts_reference_nickname or self.name
        obj = tts.reference_object(ref_nick)
        x, y = x or self.x, y or self.y
        if x and y:
            df.tts_xz(x, y, obj)
        if self.rotation:
            obj["Transform"]["rotY"] += self.rotation
        obj["Transform"]["posY"] = 2.0
        nickname = self.name
        if self.health:
            nickname = f"{self.health}/{self.health} {self.name}"
        obj["Nickname"] = nickname
        obj["Locked"] = False
        return obj

    def _ability_scores_doc(self):
        if self.strength is None:
            return None
        abilities = [
            ("Str", self.strength),
            ("Con", self.constitution),
            ("Dex", self.dexterity),
            ("Int", self.intelligence),
            ("Wis", self.wisdom),
            ("Cha", self.charisma),
        ]
        hl = []
        bl = []
        nl = []
        for name, value in abilities:
            h = str(name)
            b = int(math.floor(value / 2.0) - 5)
            if b < 0:
                b = f"{b}"
            else:
                b = f"+{b}"
            n = str(value)
            l = max(len(h), len(b), len(n))
            while len(h) < l:
                if (l - len(h)) % 2 == 1:
                    h = h + " "
                else:
                    h = " " + h
            while len(b) < l:
                if (l - len(b)) % 2 == 1:
                    b = b + " "
                else:
                    b = " " + b
            while len(n) < l:
                if (l - len(n)) % 2 == 1:
                    n = n + " "
                else:
                    n = " " + n
            hl.append(h)
            bl.append(b)
            nl.append(n)
        return Doc(
            header="Ability Scores",
            body="\n".join([" ".join(l) for l in [hl, bl, nl]]),
        )

    def _overview_doc(self):
        items = []
        lrc = []
        if self.level:
            lrc.append(f"Level {self.level}")
        if self.race:
            lrc.append(self.race)
        if self.character_class:
            lrc.append(self.character_class)
        if lrc:
            items.append(" ".join(lrc))
        if self.health:
            items.append(f"Hit Points: {self.health}")
        if self.armor_class:
            items.append(f"Armor Class: {self.armor_class}")
        if not items:
            return None
        return Doc(items)

    def _roleplay_doc(self):
        items = []
        if self.appearance:
            items.append(f"Appearance: {self.appearance}")
        if self.voice:
            items.append(f"Voice: {self.voice}")
        if self.personality:
            items.append(f"Personality: {self.personality}")
        if len(self.quirks) == 1:
            items.append(f"Quirk: {self.quirks[0]}")
        elif len(self.quirks) > 1:
            items.append(
                "\n".join(["Quirks:"] + [f"- {q}" for q in self.quirks])
            )
        if self.motivation:
            items.append(f"Motivation: {self.motivation}")
        if len(self.activities) == 1:
            items.append(f"Activity: {self.activities[0]}")
        elif len(self.activities) > 1:
            items.append(
                "\n".join(
                    ["Activities:"] + [f"- {a}" for a in self.activities]
                )
            )
        if not items:
            return None
        return Doc(items)

    def doc(self):
        header = self.name
        body = []
        doc = self._overview_doc()
        if doc:
            body.append(doc)
        doc = self._roleplay_doc()
        if doc:
            body.append(doc)
        doc = self._ability_scores_doc()
        if doc:
            body.append(doc)
        return Doc(header=header, body=body)
