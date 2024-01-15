import collections
import copy
import json
import math
import os
import pathlib
import random
import sys

import lib.trap
from lib.utils import COC_ROOT_DIR

TTS_SPAWNED_TAG = "Terrain Object Spawned by Caverns of Carl"


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


_tts_reference_save_json_memoized = None
_seen_tts_guids = set()
_tts_reference_fog = None
_tts_reference_hidden_zone = None


def tts_reference_save_json():
    global _tts_reference_save_json_memoized
    if not _tts_reference_save_json_memoized:
        filename = os.path.join(
            COC_ROOT_DIR, "reference_info", "tts", "reference_save_file.json"
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
                _seen_tts_guids.add(v)
                d[k] = new_tts_guid()
        if isinstance(v, dict) or isinstance(v, list):
            refresh_tts_guids(v)
    return d


def reference_object(nickname):
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


def dungeon_to_tts_blob(df, name, pdf_filename=None):
    blob = copy.deepcopy(tts_reference_save_json())
    blob["SaveName"] = name
    blob["GameMode"] = name
    blob["ObjectStates"] = []
    for tile in df.tile_iter():
        for obj in tile.tts_objects(df):
            df.tts_xz(tile.x, tile.y, obj)
            blob["ObjectStates"].append(obj)
    for light_source in df.light_sources:
        blob["ObjectStates"].append(light_source.tts_object(df))
    for monster in df.monsters:
        obj = monster.tts_object(df)
        blob["ObjectStates"].append(obj)
    for roomix, room in enumerate(df.rooms):
        for feature in room.special_features(df):
            blob["ObjectStates"] += feature.tts_objects(df)
        blob["ObjectStates"].append(room.tts_notecard(df))
    for corridorix, corridor in enumerate(df.corridors):
        if corridor.is_nontrivial(df):
            blob["ObjectStates"].append(corridor.tts_notecard(df))
    for trap in df.traps:
        if isinstance(trap, lib.trap.RoomTrap) or isinstance(
            trap, lib.trap.CorridorTrap
        ):
            continue
        obj = reference_object("Reference Notecard")
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
            for bit in room.tts_fog_bits():
                tmp_fog_bit_list.append(bit)
        for corridorix, corridor in enumerate(df.corridors):
            for bit in corridor.tts_fog_bits(df):
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
    # Informational PDF
    if pdf_filename:
        obj = reference_object("Reference PDF Document")
        obj["Nickname"] = "Dungeon floor information"
        obj["Description"] = ""
        obj["Transform"]["posY"] = 2.0
        obj["Locked"] = False
        obj["CustomPDF"]["PDFUrl"] = f"file:///{pdf_filename}"
        df.tts_xz(0, -5, obj)
        blob["ObjectStates"].append(obj)
    # DM's (hopefully) helpful hidden zone
    dm_fog = tts_fog(scaleX=df.width, scaleZ=20.0, hidden_zone=True)
    df.tts_xz(df.width / 2.0 - 0.5, -10.5, dm_fog)
    blob["ObjectStates"].append(dm_fog)
    # Add tags for easy mass deletion.
    for o1 in blob["ObjectStates"]:
        for o in [o1] + list(o1.get("States", {}).values()):
            tags = set(o.get("Tags", []))
            tags.add(TTS_SPAWNED_TAG)
            tags.add(f"{TTS_SPAWNED_TAG} '{name}'")
            o["Tags"] = list(tags)
    return blob


def save_tts_blob(blob):
    filename = os.path.join(
        tts_default_save_location(), blob["SaveName"] + ".json"
    )
    with open(filename, "w") as f:
        json.dump(refresh_tts_guids(blob), f, indent=2)
    return filename
