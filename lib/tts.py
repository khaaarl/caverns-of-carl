import collections
import copy
import json
import math
import os
import pathlib
import random
import sys

_COC_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
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
            _COC_ROOT_DIR, "reference_info", "tts", "reference_save_file.json"
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
