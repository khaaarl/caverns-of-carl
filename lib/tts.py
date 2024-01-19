import collections
import copy
import functools
import json
import math
import os
import pathlib
import random
import re
import sys

import lib.trap
from lib.utils import COC_ROOT_DIR

TTS_SPAWNED_TAG = "Spawned by Caverns of Carl"


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


_seen_tts_guids = set()
_tts_reference_fog = None
_tts_reference_hidden_zone = None


def recurse_object(obj):
    if obj is None:
        return
    yield obj
    for o in obj.get("States", {}).values():
        for o2 in recurse_object(o):
            yield o2
    for o in obj.get("ChildObjects", []):
        for o2 in recurse_object(o):
            yield o2
    for o in obj.get("ContainedObjects", []):
        for o2 in recurse_object(o):
            yield o2


def recurse_bag(obj):
    if obj is None:
        return
    elif isinstance(obj, list):
        for o in obj:
            for o2 in recurse_bag(o):
                yield o2
        return
    yield obj
    l = list(obj.get("ContainedObjects", []))
    l.sort(key=lambda x: x.get("Nickname") or chr(255) * 30)
    for o in recurse_bag(l):
        yield o


@functools.cache
def reference_save_json():
    filename = os.path.join(
        COC_ROOT_DIR, "reference_info", "tts", "reference_save_file.json"
    )
    with open(filename) as f:
        blob = json.load(f)
    refresh_tts_guids(blob)
    return blob


@functools.cache
def reference_objects():
    d = {}
    l = list(reference_save_json()["ObjectStates"])
    l.sort(key=lambda x: x.get("Nickname") or chr(255) * 30)
    for obj in l:
        name = obj.get("Nickname")
        if name and name not in d:
            d[name] = obj
    for obj in l:
        if obj.get("Nickname", "").startswith("Reference Bag"):
            for o2 in recurse_bag(obj):
                name = o2.get("Nickname")
                if name and name not in d:
                    d[name] = o2
    return d


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
    if nickname not in reference_objects():
        raise KeyError(
            f"Could not find nickname '{nickname}' in tts reference game"
        )
    o = copy.deepcopy(reference_objects()[nickname])
    refresh_tts_guids(o)
    return o


def tts_fog(posX=0.0, posZ=0.0, scaleX=1.0, scaleZ=1.0, hidden_zone=False):
    global _tts_reference_fog, _tts_reference_hidden_zone
    if not _tts_reference_fog:
        ref_objs = reference_save_json()["ObjectStates"]
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
        ref_objs = reference_save_json()["ObjectStates"]
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


_LUA_SCRIPT = """
function changeModelWoundCount(mod, target)
    local name = target.getName()
    local _,_, current, total = name:find("([0-9]+)/([0-9]+)")
    local newName

    if current == nil then return end

    current = math.max(tonumber(current) + mod, 0)
    total = tonumber(total)
    newName = string.gsub(name, "([0-9]+)/([0-9]+)", current.."/"..total, 1)
    
    target.setName(newName)
end


function onScriptingButtonDown(index, playerColor)
    if index ~= 2 and index ~= 3 then return end

    local player = Player[playerColor]
    local hoveredObject = player.getHoverObject()

    if not hoveredObject.hasTag("REPLACE ME") then return end
    
    if index == 2 then
      changeModelWoundCount(-1, hoveredObject)
    end
    if index == 3 then
      changeModelWoundCount(1, hoveredObject)
    end
end
""".strip()


def dungeon_to_tts_blob(df, name, pdf_filename=None):
    blob = copy.deepcopy(reference_save_json())
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
    for ix, npc in enumerate(df.npcs):
        x, y = npc.x, npc.y
        if True or x is None or y is None:
            y = -3
            x = int(df.width / 2) + ix
        obj = npc.tts_object(df, x, y)
        blob["ObjectStates"].append(obj)
    handouts = []
    for roomix, room in enumerate(df.rooms):
        for feature in room.special_features(df):
            blob["ObjectStates"] += feature.tts_objects(df)
            handouts += feature.tts_handouts()
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
    for ix, handout in enumerate(handouts):
        y = -5
        x = int(df.width / 2) + ix
        df.tts_xz(x, y, handout)
        blob["ObjectStates"].append(handout)
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
        df.tts_xz(10, -5, obj)
        blob["ObjectStates"].append(obj)
    # DM's (hopefully) helpful hidden zone
    dm_fog = tts_fog(scaleX=df.width, scaleZ=20.0, hidden_zone=True)
    df.tts_xz(df.width / 2.0 - 0.5, -10.5, dm_fog)
    blob["ObjectStates"].append(dm_fog)
    # Clear scripts if any.
    name_tag = f"{TTS_SPAWNED_TAG} '{name}'"
    for _obj in blob["ObjectStates"]:
        for obj in recurse_object(_obj):
            obj["LuaScript"] = ""
            obj["LuaScriptState"] = ""
            obj["XmlUI"] = ""
    name_tag = f"{TTS_SPAWNED_TAG} '{name}'"
    # Add HP script carrier.
    script_carrier = reference_object("Reference Notecard")
    script_carrier["LuaScript"] = re.sub("REPLACE ME", name_tag, _LUA_SCRIPT)
    script_carrier["Nickname"] = "Caverns of Carl Script Carrier"
    script_carrier["Description"] = f"Associated with dungeon '{name}'"
    script_carrier["Transform"]["posY"] = 2.0
    script_carrier["Locked"] = False
    df.tts_xz(5, -5, script_carrier)
    blob["ObjectStates"].append(script_carrier)
    # Add annotations for future easy mass deletion.
    for _obj in blob["ObjectStates"]:
        for obj in recurse_object(_obj):
            gmnotes = obj.get("GMNotes", "")
            if gmnotes:
                gmnotes += "\n\n"
            gmnotes += name_tag
            obj["GMNotes"] = gmnotes
    return blob


def save_tts_blob(blob):
    filename = os.path.join(
        tts_default_save_location(), blob["SaveName"] + ".json"
    )
    with open(filename, "w") as f:
        json.dump(refresh_tts_guids(blob), f, indent=2)
    return filename
