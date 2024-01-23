import functools
import json
import os
import random

import lib.tts as tts
from lib.tile import CorridorFloorTile, WallTile
from lib.utils import COC_ROOT_DIR, Doc


class SpecialFeature:
    def __init__(self, biome_name=None):
        self.roomix = None
        self.rand = random.random()
        self.biome_name = biome_name

    def description(self, df, verbose=False):
        """A string description of the special feature.

        This will show up in notes for its room."""
        raise NotImplementedError()

    def score_rooms(self, df):
        """Helps decide which room in which to place this feature.

        Returns a dict of room.ix : score. Score is a number (higher
        is better), and must be > 0. This dict will only include rooms that allow valid
        placement."""
        output = {}
        for room in df.rooms:
            if room.is_trivial():
                continue
            if self.biome_name and room.biome_name != self.biome_name:
                continue
            score = self.score_room(df, room)
            if score > 0.0:
                output[room.ix] = score
        return output

    def score_room(self, df, room):
        return 1.0

    def tts_objects(self, df):
        # return []
        raise NotImplementedError()

    def ascii_chars(self, df):
        """Returns a list of (x, y, char) tuples."""
        raise NotImplementedError()

    def allows_enemies(self):
        return False

    def allows_other_features(self, other_features=[]):
        return False

    def allows_treasure(self):
        return False

    def allows_traps(self):
        return False

    def mod_tts_room_tile(self, obj):
        return

    def tts_handouts(self):
        return []

    def post_process(self, df):
        return


class Blacksmith(SpecialFeature):
    def description(self, df, verbose=False):
        return "The blacksmith Andrus of Eastora has set up shop here."

    def score_room(self, df, room):
        score = 1.0
        # Prefer being in an enclosed dungeon room
        if room.tile_style() != "dungeon":
            score *= 0.5
        if not room.is_fully_enclosed_by_doors():
            score *= 0.4
        # prefer being in a bright room
        if room.light_level == "dark":
            score *= 0.1
        elif room.light_level == "dim":
            score *= 0.3
        # prefer cozy rooms
        score *= 9.0 / room.total_space()
        if not self._thing_coords(df, room):
            score = -1  # couldn't find places for my things!
        return score

    def _thing_coords(self, df, room):
        coords = list(room.tile_coords())
        offset = int(self.rand * len(coords))
        coords = coords[offset:] + coords[:offset]
        for sx, sy in coords:
            stile = df.get_tile(sx, sy)
            if stile.is_move_blocking():
                continue
            smith_near_wall = False
            smith_near_corridor = False
            ax, ay = None, None
            for atile in df.neighbor_tiles(stile):
                smith_near_wall |= isinstance(atile, WallTile)
            for atile in df.neighbor_tiles(stile, diagonal=True):
                smith_near_corridor |= isinstance(atile, CorridorFloorTile)
            if smith_near_corridor or not smith_near_wall:
                continue
            for atile in df.neighbor_tiles(stile):
                anvil_obstructed = atile.is_move_blocking()
                for nt in df.neighbor_tiles(atile, diagonal=True):
                    anvil_obstructed |= nt.is_move_blocking()
                if not anvil_obstructed:
                    ax, ay = atile.x, atile.y
                    break
            if ax:
                return {"smith_coords": (sx, sy), "anvil_coords": (ax, ay)}
        return None

    def ascii_chars(self, df):
        """Returns a list of (x, y, char) tuples."""
        room = df.rooms[self.roomix]
        thing_coords = self._thing_coords(df, room)
        sx, sy = thing_coords["smith_coords"]
        ax, ay = thing_coords["anvil_coords"]
        return [(sx, sy, "[1;97m&"), (ax, ay, "[1;97m]")]

    def tts_objects(self, df):
        room = df.rooms[self.roomix]
        thing_coords = self._thing_coords(df, room)
        sx, sy = thing_coords["smith_coords"]
        ax, ay = thing_coords["anvil_coords"]
        monster = tts.reference_object("Lich A")
        smith = tts.reference_object("Blacksmith on 1inch")
        smith["LuaScript"] = monster["LuaScript"]
        smith["Nickname"] = "Blacksmith Andrus of Eastora"
        smith["Locked"] = False
        anvil = tts.reference_object("Blacksmith's Anvil")
        anvil["Locked"] = True
        if sx > ax:
            smith["Transform"]["rotY"] += 90.0
            anvil["Transform"]["rotY"] += 90.0
        if sx < ax:
            smith["Transform"]["rotY"] -= 90.0
            anvil["Transform"]["rotY"] -= 90.0
        if sy < ay:
            smith["Transform"]["rotY"] += 180.0
            anvil["Transform"]["rotY"] += 180.0
        df.tts_xz(sx, sy, smith)
        df.tts_xz(ax, ay, anvil)
        return [smith, anvil]


@functools.cache
def deity_library():
    filename = os.path.join(
        COC_ROOT_DIR, "reference_info", "misc", "deities.json"
    )
    deities = {}
    with open(filename) as f:
        blob = json.load(f)
        for dblob in blob["Deities"]:
            deities[dblob["Name"]] = Deity(dblob)
    return deities


class Deity:
    def __init__(self, blob):
        self.name = blob["Name"]
        self.full_title = blob.get("FullTitle", self.name)
        self.tts_altar_nickname = blob["TTSAltarNickname"]
        self.minimum_door_strength = blob.get("MinimumDoorStrength")
        self.altar_descriptions = blob["AltarDescriptions"]
        self.requests = blob["Requests"]
        self.boons = blob["Boons"]
        self.ascii_color = blob["AsciiColor"]
        self.tts_tile_tint = blob.get("TTSTileTint")
        self.prefer_dark = blob.get("PreferDark", False)


class Altar(SpecialFeature):
    def __init__(self, deity_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.deity_name = deity_name
        self.deity = deity_library()[deity_name]
        self.altar_description = self.deity.altar_descriptions[0]
        self.request = self.deity.requests[0]
        self.boon = self.deity.boons[0]

    def description(self, df, verbose=False):
        if not verbose:
            return f"An altar to {self.deity_name}"
        header = f"An altar to {self.deity.full_title}"
        body = [
            self.altar_description,
            Doc("Request:", self.request),
            Doc(
                "Boon:",
                [
                    Doc(self.boon["SuccessDescription"]),
                    [Doc(self.boon["BoonHeader"], self.boon["BoonBody"])],
                ],
            ),
        ]
        return Doc(header=header, body=body)

    def score_room(self, df, room):
        if room.has_ladder():
            return -1
        if not self._thing_coords(df, room):
            return -1  # couldn't find places for my things!
        score = 1.0
        # Prefer being in an enclosed dungeon room
        if room.tile_style() != "dungeon":
            score *= 0.5
        if not room.is_fully_enclosed_by_doors():
            score *= 0.4
        # if it's kryxix, prefer being in a dark room
        if self.deity.prefer_dark:
            if room.light_level == "bright":
                score *= 0.0
            elif room.light_level == "dim":
                score *= 0.3
        # prefer cozy rooms
        score *= 9.0 / room.total_space()
        return score

    def _thing_coords(self, df, room):
        coords = list(room.tile_coords())
        offset = int(self.rand * len(coords))
        coords = coords[offset:] + coords[:offset]
        bestx, besty, bestscore = 0, 0, 0
        for ax, ay in coords:
            stile = df.get_tile(ax, ay)
            if stile.is_move_blocking():
                continue
            is_near_wall = False
            is_near_corridor = False
            for ntile in df.neighbor_tiles(stile, diagonal=True):
                is_near_wall |= isinstance(ntile, WallTile)
                is_near_corridor |= isinstance(ntile, CorridorFloorTile)
            score = 1.0
            if is_near_corridor:
                score *= 0.0
            if is_near_wall:
                score *= 0.5
            if score > bestscore:
                bestx, besty, bestscore = ax, ay, score
            if score >= 1.0:
                break
        if bestscore > 0:
            return (bestx, besty)
        return None

    def ascii_chars(self, df):
        """Returns a list of (x, y, char) tuples."""
        room = df.rooms[self.roomix]
        x, y = self._thing_coords(df, room)
        return [(x, y, self.deity.ascii_color + "&")]

    def tts_objects(self, df):
        room = df.rooms[self.roomix]
        x, y = self._thing_coords(df, room)
        altar = tts.reference_object("Generic Altar")
        altar["Locked"] = True
        df.tts_xz(x, y, altar)
        altar["Transform"]["posY"] = 2.6
        altar["Nickname"] = self.deity.tts_altar_nickname
        altar["Description"] = ""
        return [altar]

    def tts_handouts(self):
        obj = tts.reference_object(self.boon["TTSHandoutReferenceObject"])
        obj["Nickname"] = self.boon["BoonHeader"]
        obj["Description"] = self.boon["BoonBody"]
        return [obj]

    def mod_tts_room_tile(self, obj):
        color_muls = self.deity.tts_tile_tint
        if not color_muls:
            return
        ref_floor = tts.reference_object("Floor, Dungeon")
        ref_mesh = ref_floor["CustomMesh"]["MeshURL"]
        for o in tts.recurse_object(obj):
            if o.get("CustomMesh", {}).get("MeshURL") == ref_mesh:
                for k in "rgb":
                    o["ColorDiffuse"][k] *= color_muls[k]

    def post_process(self, df):
        if self.deity.minimum_door_strength:
            room = df.rooms[self.roomix]
            for doorix in room.doorixs:
                df.doors[doorix].apply_minimum_door_strength(
                    self.deity.minimum_door_strength
                )
