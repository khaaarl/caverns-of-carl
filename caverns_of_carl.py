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
* monster encounter constraint: Frontline (done)
* cavernous rooms (done)
* room lighting, denoted with floor tile tint & description
* ladder configurable bfs distance check
* cavernous corridors should have some erosion, and not be straight
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
import json
import math
import os
import random
import re
import traceback

try:
    import tkinter as _tk_test
except:
    print(
        "Failed to load tcl/tk. You may need to install additional modules (e.g. python3-tk if you are on Ubuntu)\nPress enter to exit"
    )
    input()
    exit()

import tkinter as tk
import tkinter.font
from tkinter import scrolledtext
from tkinter import ttk

from lib.monster import get_monster_library, Monster
from lib.tile import (
    BookshelfTile,
    ChestTile,
    CorridorFloorTile,
    DoorTile,
    LadderUpTile,
    LadderDownTile,
    MimicTile,
    RoomFloorTile,
    Tile,
    WallTile,
)
import lib.features
import lib.trap
from lib.treasure import get_treasure_library
import lib.tts as tts
from lib.tts import (
    TTSFogBit,
    TTS_SPAWNED_TAG,
    refresh_tts_guids,
    tts_default_save_location,
    tts_reference_save_json,
    tts_fog,
)
from lib.utils import bfs, choice, dfs, eval_dice, samples


class RetriableDungeonographyException(Exception):
    pass


class RetriableRoomPlacementException(RetriableDungeonographyException):
    pass


class RetriableCorridorPlacementException(RetriableDungeonographyException):
    pass


class RetriableFeaturePlacementException(RetriableDungeonographyException):
    pass


class Room:
    def __init__(self, x, y, rw=1, rh=1):
        self.x = x
        self.y = y
        self.rw = int(max(rw, 1))
        self.rh = int(max(rh, 1))
        self.light_level = "bright"  # or "dim" or "dark"
        self.has_up_ladder = False
        self.has_down_ladder = False
        self.ix = None
        self.encounter = None
        self.special_featureixs = []
        self.doorixs = set()
        self.trapixs = set()

    def embiggened(self):
        return self.__class__(
            self.x,
            self.y,
            self.rw + random.randrange(2),
            self.rh + random.randrange(2),
        )

    def wiggled(self):
        return self.__class__(
            self.x + random.randrange(-1, 2),
            self.y + random.randrange(-1, 2),
            self.rw,
            self.rh,
        )

    def tile_style(self):
        return "dungeon"

    def new_floor_tile(self):
        t = RoomFloorTile(self.ix)
        t.tile_style = "dungeon"
        return t

    def apply_to_tiles(self, df):
        for x, y in self.tile_coords():
            df.set_tile(self.new_floor_tile(), x=x, y=y)

    def remove_from_tiles(self, df):
        for x, y in self.tile_coords():
            df.set_tile(WallTile(), x=x, y=y)

    def tile_coords(self):
        raise NotImplementedError()

    def has_ladder(self):
        return self.has_up_ladder or self.has_down_ladder

    def special_features(self, df):
        for featureix in self.special_featureixs:
            yield df.special_features[featureix]

    def allows_treasure(self, df):
        if self.has_ladder():
            return False
        for feature in self.special_features(df):
            if not feature.allows_treasure():
                return False
        return True

    def allows_enemies(self, df):
        if self.has_ladder():
            return False
        for feature in self.special_features(df):
            if not feature.allows_enemies():
                return False
        return True

    def allows_traps(self, df):
        if self.has_ladder():
            return False
        for feature in self.special_features(df):
            if not feature.allows_traps():
                return False
        return True

    def pick_tile(
        self,
        df,
        unoccupied=False,
        avoid_corridor=False,
        prefer_wall=False,
        avoid_wall=False,
        diameter=1,
    ):
        coords = list(self.tile_coords())
        for _ in range(100):
            x, y = random.choice(coords)

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
                    found_wall = False
                    for dtile in df.neighbor_tiles(tx, ty, WallTile):
                        if isinstance(dtile, CorridorFloorTile):
                            found_problem |= avoid_corridor
                        if isinstance(dtile, WallTile):
                            found_problem |= avoid_wall
                            found_wall = True
                    found_problem |= not found_wall and prefer_wall
                    if found_problem:
                        break
            if not found_problem:
                return (x, y)
        return None

    def is_trivial(self):
        return False

    def total_space(self):
        return len(self.tile_coords())

    def tts_fog_bits(self):
        """returns a list of fog bits: a big central one, and a small one for each border grid space."""
        fogs = []
        used_coords = set()
        for x, y in self.tile_coords():
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    tx, ty = x + dx, y + dy
                    priority = 1
                    if tx == self.x and ty == self.y:
                        priority = 2
                    if (tx, ty) not in used_coords:
                        fogs.append(
                            TTSFogBit(
                                tx, ty, roomixs=[self.ix], priority=priority
                            )
                        )
                        used_coords.add((tx, ty))
        return fogs

    def description(self, df, verbose=False):
        o = []
        if self.has_down_ladder:
            o.append("Down ladder")
        if self.has_up_ladder:
            o.append("Up ladder")
        for featureix in self.special_featureixs:
            o.append(df.special_features[featureix].description(df))
        for trapix in self.trapixs:
            o.append(df.traps[trapix].description())
        o.append(f"Light level: {self.light_level.capitalize()}")
        if verbose:
            if self.encounter:
                xp = self.encounter.total_xp()
                pct = int(round(100.0 * xp / med_target_xp(df.config)))
                s = [f"Monster encounter (~{xp:,} xp; ~{pct}% of Medium):"]
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
        return "\n\n".join(o)

    def tts_notecard(self, df):
        obj = tts.reference_object("Reference Notecard")
        obj["Nickname"] = f"DM/GM notes for room {self.ix}"
        obj["Description"] = self.description(df)
        obj["Transform"]["posY"] = 4.0
        obj["Locked"] = True
        df.tts_xz(self.x, self.y, obj)
        return obj

    def is_fully_enclosed_by_doors(self):
        return NotImplementedError()


class RectRoom(Room):
    def tile_coords(self):
        for x in range(self.x - self.rw, self.x + self.rw + 1):
            for y in range(self.y - self.rh, self.y + self.rh + 1):
                yield (x, y)

    def total_space(self):
        return (1 + self.rw * 2) * (1 + self.rh * 2)

    def is_fully_enclosed_by_doors(self):
        return True


class CavernousRoom(Room):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.explicit_tile_coords = None

    def tile_style(self):
        return "cavern"

    def new_floor_tile(self):
        t = RoomFloorTile(self.ix)
        t.tile_style = "cavern"
        return t

    def tile_coords(self):
        if self.explicit_tile_coords is None:
            self.explicit_tile_coords = []
            for x in range(self.x - self.rw, self.x + self.rw + 1):
                for y in range(self.y - self.rh, self.y + self.rh + 1):
                    dx = (x - self.x) ** 2 / (self.rw + 0.5) ** 2
                    dy = (y - self.y) ** 2 / (self.rh + 0.5) ** 2
                    if dx + dy <= 1.0:
                        self.explicit_tile_coords.append((x, y))
        return self.explicit_tile_coords

    def is_fully_enclosed_by_doors(self):
        return False

    def erode(self, df, num_iterations=5, per_tile_chance=0.25):
        for _ in range(num_iterations):
            self._erode_single(df, per_tile_chance)

    def _erode_single(self, df, per_tile_chance):
        outer_coords = set()
        wall_coords = set()
        for x, y in self.tile_coords():
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                tx, ty = x + dx, y + dy
                if isinstance(df.tiles[tx][ty], WallTile):
                    outer_coords.add((x, y))
                    wall_coords.add((tx, ty))
        erodable = []
        for x, y in wall_coords:
            # wtile = df.tiles[x][y]
            safe_to_expand = True
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    tx, ty = x + dx, y + dy
                    if tx <= 0 or tx >= df.width or ty <= 0 or ty >= df.height:
                        safe_to_expand = False
                        break
                    if (tx, ty) in outer_coords:
                        continue
                    if isinstance(df.tiles[tx][ty], RoomFloorTile):
                        # found another room, oughtn't expand
                        safe_to_expand = False
                        break
            if safe_to_expand:
                erodable.append((x, y))
        for x, y in erodable:
            if random.random() < per_tile_chance:
                self.explicit_tile_coords.append((x, y))
                df.set_tile(self.new_floor_tile(), x=x, y=y)


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
        self.light_level = "bright"  # or "dim" or "dark"
        self.ix = None
        self.doorixs = set()
        self.trapixs = set()
        self.name = None

    def is_fully_enclosed_by_doors(self):
        return len(self.doorixs) >= 2

    def tile_style(self):
        return "dungeon"

    def walk(self, max_width_iter=None):
        return CorridorWalker(self, max_width_iter=max_width_iter)

    def tile_coords(self, df, include_doors=False):
        for x, y in self.walk():
            tile = df.tiles[x][y]
            if isinstance(tile, DoorTile):
                if include_doors:
                    yield (x, y)
                else:
                    continue
            if isinstance(tile, CorridorFloorTile):
                yield (x, y)

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
        o.append(f"Light level: {self.light_level.capitalize()}")
        if verbose:
            for doorix in self.doorixs:
                door = df.doors[doorix]
                assert len(door.roomixs) == 1
                roomix = list(door.roomixs)[0]
                s = f"Door to Room {roomix}"
                for trapix in door.trapixs:
                    s += "\n" + df.traps[trapix].description()
                o.append(s)
        return "\n\n".join(o)

    def tts_notecard(self, df):
        obj = tts.reference_object("Reference Notecard")
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

    def tts_fog_bits(self, df):
        """returns a list of fog bits: all small ones probably."""
        fogs = []
        num_blank_corridor_tiles = 0
        # walked places
        for x, y in self.walk():
            tile = df.tiles[x][y]
            if isinstance(tile, CorridorFloorTile):
                if not isinstance(tile, DoorTile):
                    num_blank_corridor_tiles += 1
                fogs.append(TTSFogBit(x, y, corridorixs=[self.ix]))
                for nt in df.neighbor_tiles(x, y, diagonal=True):
                    if isinstance(nt, WallTile):
                        fogs.append(
                            TTSFogBit(nt.x, nt.y, corridorixs=[self.ix])
                        )
        if num_blank_corridor_tiles == 0:
            return []
        return fogs


class CavernousCorridor(Corridor):
    def is_fully_enclosed_by_doors(self):
        return False

    def tile_style(self):
        return "cavern"


class Door:
    def __init__(self, x, y, corridorix, roomixs=None):
        self.x, self.y = x, y
        self.corridorix = corridorix
        self.roomixs = set(roomixs or [])
        self.trapixs = set()
        self.ix = None


class LightSource:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.roomix = None
        self.corridorix = None
        self.ix = None

    def tts_object(self, df):
        raise NotImplementedError()


class WallSconce(LightSource):
    def tts_object(self, df):
        obj = tts.reference_object("Horn Candle Sconce")
        df.tts_xz(self.x, self.y, obj)
        obj["Transform"]["rotX"] = 0.0
        obj["Transform"]["rotY"] = 0.0
        obj["Transform"]["rotZ"] = 0.0
        obj["Transform"]["posY"] = 1.8
        obj["Transform"]["scaleX"] = 0.7
        obj["Transform"]["scaleY"] = 0.7
        obj["Transform"]["scaleZ"] = 0.7
        obj["Locked"] = True
        # Rotate away from wall
        posrots = [(0, 1, 90), (1, 0, 180), (0, -1, 270), (-1, 0, 0)]
        random.shuffle(posrots)
        for dx, dy, r in posrots:
            if isinstance(df.tiles[self.x + dx][self.y + dy], WallTile):
                obj["Transform"]["rotY"] += r
                obj["Transform"]["posX"] += 0.5 * dx
                obj["Transform"]["posZ"] += 0.5 * dy
                break
        # Currently the attached light ... doesn't look very good.
        del obj["ChildObjects"]
        return obj


class GlowingMushrooms(LightSource):
    def tts_object(self, df):
        obj = tts.reference_object("Blue Mushrooms for Glowing")
        df.tts_xz(self.x, self.y, obj)
        obj["Transform"]["rotX"] = 0.0
        obj["Transform"]["rotY"] = random.randrange(360) * 1.0
        obj["Transform"]["rotZ"] = 0.0
        obj["Transform"]["posY"] = 2.0
        obj["Transform"]["scaleX"] = 0.5
        obj["Transform"]["scaleY"] = 0.5
        obj["Transform"]["scaleZ"] = 0.5
        obj["Locked"] = True
        # Currently the attached light ... doesn't look very good.
        del obj["ChildObjects"]
        return obj


def neighbor_coords(x, y, cardinal=True, diagonal=False):
    l = []
    if cardinal:
        l += [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if diagonal:
        l += [(-1, -1), (1, -1), (-1, 1), (1, 1)]
    for dx, dy in l:
        yield (x + dx, y + dy)


class DungeonFloor:
    def __init__(self, config):
        self.config = config
        self.width = config.width
        self.height = config.height
        # tiles[x][y] points to a tile on the map. Indexed [0, width) and [0, height)
        self.tiles = [
            [WallTile(x, y) for y in range(self.height)]
            for x in range(self.width)
        ]
        self.rooms = []
        self.corridors = []
        self.doors = []
        self.special_features = []
        self.monsters = []
        self.traps = []
        self.light_sources = []
        self.monster_locations = {}  # (x, y) -> monster
        # a graph of rooms' neighbors, from room index to set of
        # neighbors' room indices.
        self.room_neighbors = collections.defaultdict(set)

    def tts_xz(self, x, y, tts_transform=None, diameter=1):
        tts_x = x - math.floor(self.width / 2.0) + 0.5
        tts_z = y - math.floor(self.height / 2.0) + 0.5
        if diameter % 2 == 0:
            # offset for wider models that aren't centered
            tts_x += 0.5
            tts_z += 0.5
        if tts_transform:
            if "Transform" in tts_transform:
                tts_transform = tts_transform["Transform"]
            tts_transform["posX"] = tts_x
            tts_transform["posZ"] = tts_z
        return (tts_x, tts_z)

    def random_room(self):
        r = int(max(1, self.config.min_room_radius))
        cls = RectRoom
        if random.random() * 100.0 < self.config.cavernous_room_percent:
            cls = CavernousRoom
        return cls(
            x=random.randrange(1 + r, self.width - 1 - r),
            y=random.randrange(1 + r, self.height - 1 - r),
            rw=r,
            rh=r,
        )

    def tile_iter(self):
        for y in range(self.height - 1, -1, -1):
            for x in range(self.width):
                yield self.tiles[x][y]

    def set_tile(self, tile, x=None, y=None):
        if x is not None:
            tile.x = x
        if y is not None:
            tile.y = y
        assert tile.x is not None and tile.y is not None
        if tile.corridorix is None and tile.roomix is None:
            prev_tile = self.tiles[x][y]
            tile.roomix = prev_tile.roomix
            tile.corridorix = prev_tile.corridorix
        assert tile.x >= 0
        assert tile.x < self.width
        assert tile.y >= 0
        assert tile.y <= self.height
        self.tiles[x][y] = tile
        return tile

    def get_tile(self, x, y, default=None):
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            if default is None:
                return None
            if isinstance(default, Tile):
                return default
            else:  # assume it's a tile class
                return default(x=x, y=y)
        return self.tiles[x][y]

    def neighbor_tiles(
        self, x, y=None, default=None, cardinal=True, diagonal=False
    ):
        if isinstance(x, Tile):
            y = x.y
            x = x.x
        for tx, ty in neighbor_coords(x, y, cardinal, diagonal):
            tile = self.get_tile(tx, ty, default)
            if tile:
                yield tile

    def add_room(self, room):
        room.ix = len(self.rooms)
        self.rooms.append(room)
        room.apply_to_tiles(self)

    def add_corridor(self, corridor):
        corridor.ix = len(self.corridors)
        self.corridors.append(corridor)
        self.room_neighbors[corridor.room1ix].add(corridor.room2ix)
        self.room_neighbors[corridor.room2ix].add(corridor.room1ix)
        for x, y in corridor.walk():
            if isinstance(self.tiles[x][y], WallTile):
                self.set_tile(CorridorFloorTile(corridor.ix), x=x, y=y)

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
        for feature in self.special_features:
            for x, y, c in feature.ascii_chars(self):
                chars[x][y] = c
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
        o = []
        for t in self.tile_iter():
            if t.x == 0 and t.y < self.height - 1:
                o.append("\n")
            o.append(chars[t.x][t.y])
        return "".join(o)


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
        self.add_var("cavernous_room_percent", 50.0)
        self.add_var("room_bright_ratio", 5.0)
        self.add_var("room_dim_ratio", 2.0)
        self.add_var("room_dark_ratio", 1.0)
        self.add_var("num_erosion_steps", 4)
        self.add_var("prefer_full_connection", True)
        self.add_var("min_corridors_per_room", 1.1)
        self.add_var("corridor_width_1_ratio", 1.0)
        self.add_var("corridor_width_2_ratio", 5.0)
        self.add_var("corridor_width_3_ratio", 2.0)
        self.add_var("num_up_ladders", 1)
        self.add_var("num_down_ladders", 1)
        self.add_var("min_ladder_distance", 2)
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
        self.add_var("blacksmith_percent", 30.0)
        self.allow_corridor_intersection = False
        self.min_ladder_distance = 2
        self.max_corridor_attempts = 30000
        self.max_room_attempts = 10

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


def generate_random_dungeon(config=None, errors=None):
    config = config or DungeonConfig()
    errors = errors or []
    successful = False
    for _ in range(100):
        try:
            df = DungeonFloor(config)
            place_rooms_in_dungeon(df)
            erode_cavernous_rooms_in_dungeon(df)
            place_corridors_in_dungeon(df)
            place_doors_in_dungeon(df)
            place_ladders_in_dungeon(df)
            place_special_features_in_dungeon(df)
            place_treasure_in_dungeon(df)
            place_monsters_in_dungeon(df)
            place_traps_in_dungeon(df)
            place_lights_in_dungeon(df)
            stylize_tiles_in_dungeon(df)
        except RetriableDungeonographyException as err:
            errors.append(err)
        else:
            successful = True
        if successful:
            break
    if successful:
        return df
    raise errors[-1]


def place_rooms_in_dungeon(df):
    config = df.config
    rooms = []
    for _ in range(config.max_room_attempts * config.num_rooms):
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
    if len(rooms) < config.num_rooms:
        raise RetriableRoomPlacementException(
            f"Failed to place all requested rooms ({len(rooms)} of {config.num_rooms})"
        )

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
    # apply light levels
    for room in rooms:
        room.light_level = choice(
            ["bright", "dim", "dark"],
            weights=[
                config.room_bright_ratio,
                config.room_dim_ratio,
                config.room_dark_ratio,
            ],
        )
    # sort rooms from top to bottom so their indices are more human comprehensible maybe
    rooms.sort(key=lambda r: (-r.y, r.x))
    # add rooms to dungeon floor
    for room in rooms:
        df.add_room(room)


def erode_cavernous_rooms_in_dungeon(df):
    for room in df.rooms:
        if isinstance(room, CavernousRoom):
            room.erode(df, num_iterations=df.config.num_erosion_steps)


def place_corridors_in_dungeon(df):
    config = df.config
    rooms_connected = {}
    is_fully_connected = False
    prev_attempts = set()
    for _ in range(config.max_corridor_attempts):
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
        is_horizontal_first = random.randrange(2)

        width = choice(
            [1, 2, 3],
            weights=[
                config.corridor_width_1_ratio,
                config.corridor_width_2_ratio,
                config.corridor_width_3_ratio,
            ],
        )
        signature = (room1ix, room2ix, width, is_horizontal_first)
        if signature in prev_attempts:
            continue
        prev_attempts.add(signature)

        room1 = df.rooms[room1ix]
        room2 = df.rooms[room2ix]
        cls = Corridor
        if isinstance(room1, CavernousRoom) and isinstance(
            room2, CavernousRoom
        ):
            cls = CavernousCorridor
        corridor = cls(
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
                proom = None
                penclose = None
                if isinstance(ptile, RoomFloorTile):
                    proom = df.rooms[ptile.roomix]
                    penclose = proom.is_fully_enclosed_by_doors()
                nroom = None
                nenclose = None
                if isinstance(ntile, RoomFloorTile):
                    nroom = df.rooms[ntile.roomix]
                    nenclose = nroom.is_fully_enclosed_by_doors()
                if proom and nroom:
                    if not penclose and not nenclose:
                        continue
                elif proom and not penclose or nroom and not nenclose:
                    continue
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
                    for x2 in range(-1, 2):
                        for y2 in range(-1, 2):
                            reqd_walls.append((x + x2, y + y2))
                for x2, y2 in reqd_walls:
                    if not isinstance(df.tiles[x2][y2], WallTile):
                        found_problem = True
                        break
        if not found_problem:
            # set light level to in between the two rooms
            light_levels = sorted([room1.light_level, room2.light_level])
            corridor.light_level = random.choice(light_levels)
            if light_levels == ["bright", "dark"]:
                corridor.light_level = "dim"
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
    if config.prefer_full_connection and len(dfs(df.room_neighbors, 0)) < len(
        df.rooms
    ):
        raise RetriableCorridorPlacementException(
            "Failed to construct corridors with fully connected rooms."
        )
    sorted_corridors = [
        (c, c.middle_coords(df)) for c in df.corridors if c.is_nontrivial(df)
    ]
    sorted_corridors.sort(key=lambda p: (-p[1][1], p[1][0]))
    for ix, p in enumerate(sorted_corridors):
        corridor = p[0]
        corridor.name = f"C{ix+1}"


def place_doors_in_dungeon(df):
    for corridor in df.corridors:
        if isinstance(corridor, CavernousCorridor):
            continue  # caverns don't have doors
        room1 = df.rooms[corridor.room1ix]
        room2 = df.rooms[corridor.room2ix]
        corridor_coords = list(corridor.walk(max_width_iter=1))
        new_door_locations = set()  # x, y, dx, dy
        for ix in range(1, len(corridor_coords) - 1):
            x, y = corridor_coords[ix]
            px, py = corridor_coords[ix - 1]
            nx, ny = corridor_coords[ix + 1]
            tile = df.tiles[x][y]
            ptile = df.tiles[px][py]
            ntile = df.tiles[nx][ny]
            if (
                ptile.roomix == room1.ix
                and room1.is_fully_enclosed_by_doors()
                and isinstance(tile, CorridorFloorTile)
            ) or (
                not isinstance(ptile, DoorTile)
                and isinstance(tile, CorridorFloorTile)
                and ntile.roomix == room2.ix
                and room2.is_fully_enclosed_by_doors()
            ):
                df.set_tile(DoorTile(corridor.ix), x=x, y=y)
                new_door_locations.add((x, y, x - px, y - py))
        for x, y, dx, dy in new_door_locations:
            rx, ry = x, y
            lx, ly = x, y
            if dx != 0:
                ry += 1
                ly -= 1
            else:
                rx += 1
                lx -= 1
            for tx, ty in [(rx, ry), (lx, ly)]:
                tile = df.get_tile(tx, ty)
                if isinstance(tile, DoorTile):
                    continue
                if isinstance(tile, CorridorFloorTile):
                    df.set_tile(DoorTile(corridor.ix), x=tx, y=ty)
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


def place_ladders_in_dungeon(df):
    max_depth = df.config.min_ladder_distance - 1
    target_n_ladders = df.config.num_up_ladders + df.config.num_down_ladders
    ladder_room_ixs = set()
    roomix_tile_coords = {}
    rooms = [x for x in df.rooms if not x.is_trivial()]
    random.shuffle(rooms)

    # bias ourselves towards smallest rooms
    rooms.sort(key=lambda x: x.total_space())
    while len(rooms) < 2 * len(df.rooms) - 3:
        rooms = rooms + rooms[: int((2 * len(df.rooms) - len(rooms)) / 2 + 1)]

    max_attempts = 50
    for attempt_ix in range(max_attempts):
        if len(ladder_room_ixs) >= target_n_ladders:
            break
        ladder_room_ixs = set()
        roomix_tile_coords = {}
        for _ in range(
            10 * (df.config.num_up_ladders + df.config.num_down_ladders)
        ):
            if len(ladder_room_ixs) >= target_n_ladders:
                break
            room = random.choice(rooms)
            if room.ix in ladder_room_ixs:
                continue
            # BFS check on ladders to be a configurable distance
            # apart. If it's a late attempt, ignore BFS.
            found_problem = False
            for layer in bfs(df.room_neighbors, room.ix, max_depth):
                for otherix in layer:
                    if otherix in ladder_room_ixs:
                        found_problem = True
            if found_problem and attempt_ix * 2 < max_attempts:
                continue
            tile_coords = room.pick_tile(
                df, unoccupied=True, avoid_corridor=True, avoid_wall=True
            )
            if not tile_coords:
                continue
            ladder_room_ixs.add(room.ix)
            roomix_tile_coords[room.ix] = tile_coords
    ladder_room_ixs = list(ladder_room_ixs)
    random.shuffle(ladder_room_ixs)
    num_up_ladders = 0
    for roomix in ladder_room_ixs:
        room = df.rooms[roomix]
        x, y = roomix_tile_coords[roomix]

        if num_up_ladders < df.config.num_up_ladders:
            df.set_tile(LadderUpTile(roomix), x=x, y=y)
            room.has_up_ladder = True
            num_up_ladders += 1
        else:
            df.set_tile(LadderDownTile(roomix), x=x, y=y)
            room.has_down_ladder = True


def place_special_features_in_dungeon(df):
    features = []
    if random.random() < df.config.blacksmith_percent / 99.9:
        features.append(lib.features.Blacksmith())
    feature_roomix_scores = []
    transposed_feature_roomix_scores = []
    for feature in features:
        scores = feature.score_rooms(df)
        feature_roomix_scores.append(scores)
        roomix_scores = sorted(scores.items())
        if not roomix_scores:
            raise RetriableFeaturePlacementException()
        transposed_feature_roomix_scores.append(list(zip(*roomix_scores)))
    feature_ixs = list(range(len(features)))
    best_score = None
    best_placement = []  # featureix -> roomix
    for _ in range(100):
        roomixs_used = set()
        feature_ixs = list(range(len(features)))
        random.shuffle(feature_ixs)
        score = 1.0
        feature_room_choices = [-1] * len(features)
        for fix in feature_ixs:
            feature = features[fix]
            rixs, weights = transposed_feature_roomix_scores[fix]
            k = min(len(roomixs_used) + 1, len(rixs))
            for rix in samples(rixs, weights=weights, k=k):
                if rix not in roomixs_used:
                    feature_room_choices[fix] = rix
                    score *= feature_roomix_scores[fix][rix]
                    roomixs_used.add(rix)
                    break
            if feature_room_choices[fix] < 0:
                score = 0.0
                break
        if score > 0.0 and (best_score is None or score > best_score):
            best_score = score
            best_placement = feature_room_choices
    if best_score is None:
        raise RetriableFeaturePlacementException()
    df.special_features = features
    for fix, roomix in enumerate(best_placement):
        room = df.rooms[roomix]
        room.special_featureixs.append(fix)
        features[fix].roomix = roomix


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
    max_attempts = (
        target_num_treasures + target_num_bookshelves + target_num_mimics
    ) * 10
    for _ in range(max_attempts):
        if (
            num_treasures >= target_num_treasures
            and num_bookshelves >= target_num_bookshelves
            and num_mimics >= target_num_mimics
        ):
            return
        roomix = random.choice(sized_roomixs)
        room = df.rooms[roomix]
        if not room.allows_treasure(df):
            continue
        coords = room.pick_tile(
            df, unoccupied=True, avoid_corridor=True, prefer_wall=True
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
            df.set_tile(
                ChestTile(roomix, contents="\n".join(contents)), x=x, y=y
            )
            num_treasures += 1
        elif num_mimics < target_num_mimics:
            monster = Monster(mimic_info)
            monster.adjust_cr(df.config.target_character_level)
            df.set_tile(MimicTile(roomix, monster=monster), x=x, y=y)
            num_mimics += 1
        elif num_bookshelves < target_num_bookshelves:
            if isinstance(room, CavernousRoom):
                continue  # caverns don't have bookshelves
            contents = lib.gen_bookshelf_horde(
                df.config.target_character_level,
                df.config.num_player_characters,
            )
            if not contents:
                contents = ["Nothing!"]
            df.set_tile(
                BookshelfTile(roomix, contents="\n".join(contents)), x=x, y=y
            )
            num_bookshelves += 1


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
    for roomix, room in enumerate(df.rooms):
        if room.allows_enemies(df):
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
        if room.allows_traps(df):
            roomixs_to_trap.append(roomix)
    random.shuffle(roomixs_to_trap)
    for roomix in roomixs_to_trap[:target_num_room_traps]:
        room = df.rooms[roomix]
        trap = lib.trap.RoomTrap.create(config, room)
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
        corridor = df.corridors[corridorix]
        trap = lib.trap.CorridorTrap.create(config, corridor)
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
        trap = lib.trap.DoorTrap.create(config, door.ix, door.x, door.y)
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
        trap = lib.trap.ChestTrap.create(config, x, y)
        df.add_trap(trap)
        df.tiles[x][y].trapixs.add(trap.ix)


def place_lights_in_dungeon(df):
    thing_tiles = []
    for room in df.rooms:
        l = []
        for x, y in room.tile_coords():
            tile = df.tiles[x][y]
            l.append((tile, x, y))
        thing_tiles.append((room, l))
    for corridor in df.corridors:
        l = []
        for x, y in corridor.tile_coords(df, include_doors=True):
            tile = df.tiles[x][y]
            l.append((tile, x, y))
        thing_tiles.append((corridor, l))
    for thing, l in thing_tiles:
        for tile, x, y in l:
            tile.light_level = thing.light_level
        if thing.light_level == "dark":
            continue
        thing_lights = []
        if isinstance(thing, CavernousRoom) or isinstance(
            thing, CavernousCorridor
        ):
            cs = [x for x in l if not isinstance(x[0], DoorTile)]
            random.shuffle(cs)
            denom = 20.0
            if thing.light_level == "bright":
                denom = 10.0
            for tile, x, y in cs[: max(1, int(len(cs) / denom))]:
                thing_lights.append(GlowingMushrooms(x, y))
        else:
            cs = []
            for tile, x, y in l:
                num_near_walls = 0
                for nt in df.neighbor_tiles(x, y, WallTile):
                    if isinstance(nt, WallTile):
                        num_near_walls += 1
                if num_near_walls < 1 or isinstance(tile, DoorTile):
                    continue
                if isinstance(room, BookshelfTile):
                    continue
                cs.append((tile, x, y))
            random.shuffle(cs)
            denom = 6.0
            if thing.light_level == "bright":
                denom = 3.0
            for tile, x, y in cs[: max(1, int(len(cs) / denom))]:
                thing_lights.append(WallSconce(x, y))
        for light in thing_lights:
            if isinstance(thing, Room):
                light.roomix = thing.ix
            else:
                light.corridorix = thing.ix
            df.light_sources.append(light)


def stylize_tiles_in_dungeon(df):
    for room in df.rooms:
        for x, y in room.tile_coords():
            df.tiles[x][y].tile_style = room.tile_style()
            for tile in df.neighbor_tiles(x, y, diagonal=True):
                if not tile.tile_style or room.tile_style() == "dungeon":
                    tile.tile_style = room.tile_style()
    for corridor in df.corridors:
        for x, y in corridor.tile_coords(df, include_doors=True):
            df.tiles[x][y].tile_style = corridor.tile_style()
            for tile in df.neighbor_tiles(x, y, diagonal=True):
                if not (
                    isinstance(tile, CorridorFloorTile)
                    or isinstance(tile, WallTile)
                ):
                    continue
                if not tile.tile_style or corridor.tile_style() == "dungeon":
                    tile.tile_style = corridor.tile_style()

    unstyled = set()
    for x in range(df.width):
        for y in range(df.height):
            if df.tiles[x][y].tile_style is None:
                unstyled.add((x, y))
    while unstyled:
        for x, y in list(unstyled):
            style_counts = collections.defaultdict(int)
            for dtile in df.neighbor_tiles(x, y):
                if dtile.tile_style is not None:
                    style_counts[dtile.tile_style] += 1
            if not style_counts:
                continue
            tile = df.tiles[x][y]
            n = sum(style_counts.values())
            m = max(style_counts.values())
            style_counts = list(style_counts.items())
            style_counts.sort(key=lambda x: x[1])
            if m / n > 0.7:
                tile.tile_style = style_counts[-1][0]
            else:
                p = random.randrange(n)
                for s, k in style_counts:
                    if p < k:
                        tile.tile_style = s
                        break
                    p -= k
            if tile.tile_style is not None:
                tile.is_interior = True
                unstyled.remove((x, y))


def dungeon_to_tts_blob(df):
    name = f"Caverns of Carl {datetime.datetime.now():%Y-%m-%dT%H-%M-%S%z}"
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
        obj = tts.reference_object("Reference Notecard")
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
            total_xp = 0
            for room in df.rooms:
                if room.encounter:
                    total_xp += room.encounter.total_xp()
            xp_per_player = int(total_xp / config.num_player_characters)
            text_output.append(
                f"Total floor encounter xp: ~{total_xp:,} (~{xp_per_player:,} per player)"
            )
            text_output.append("")
            for room in df.rooms:
                text_output.append(f"***Room {room.ix}***")
                text_output.append(room.description(df, verbose=True))
                text_output.append("")
            for corridor in sorted(df.corridors, key=lambda x: x.name or ""):
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
