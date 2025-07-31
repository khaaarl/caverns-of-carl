import random

import lib.tts as tts
from lib.tile import (
    BookshelfTile,
    ChestTile,
    CorridorFloorTile,
    MimicTile,
    RoomFloorTile,
    WallTile,
)
from lib.tts import TTSFogBit
from lib.utils import Doc, DocBookmark, DocLink


class Room:
    def __init__(self, x, y, rw=1, rh=1, biome_name=None):
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
        self.corridorixs = set()
        self.doorixs = set()
        self.trapixs = set()
        self.biome_name = biome_name
        self.in_maze = False
        self.name_num = None

    def embiggened(self):
        return self.__class__(
            self.x,
            self.y,
            self.rw + random.randrange(2),
            self.rh + random.randrange(2),
            biome_name=self.biome_name,
        )

    def wiggled(self):
        return self.__class__(
            self.x + random.randrange(-1, 2),
            self.y + random.randrange(-1, 2),
            self.rw,
            self.rh,
            biome_name=self.biome_name,
        )

    def tile_style(self):
        return "dungeon"

    def new_floor_tile(self):
        t = RoomFloorTile(self.ix, biome_name=self.biome_name)
        t.tile_style = self.tile_style()
        return t

    def apply_to_tiles(self, df):
        for x, y in self.tile_coords():
            df.set_tile(self.new_floor_tile(), x=x, y=y)

    def remove_from_tiles(self, df):
        for x, y in self.tile_coords():
            df.set_tile(WallTile(biome_name=self.biome_name), x=x, y=y)

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

    def allows_bookshelf(self, df):
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

    def tts_fog_bits(self, df):
        """returns a list of fog bits: a big central one, and a small one for each border grid space."""
        fogs = []
        used_coords = set()
        for x, y in self.tile_coords():
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    tx, ty = x + dx, y + dy
                    if (tx, ty) in used_coords:
                        continue
                    used_coords.add((tx, ty))
                    tile = df.get_tile(tx, ty)
                    if not tile or tile.riverixs:
                        continue
                    priority = 1
                    if tx == self.x and ty == self.y:
                        priority = 2
                    fogs.append(
                        TTSFogBit(tx, ty, roomixs=[self.ix], priority=priority)
                    )
        return fogs

    def description(self, df, verbose=False):
        o = []
        if self.has_down_ladder:
            o.append("Down ladder")
        if self.has_up_ladder:
            o.append("Up ladder")
        for featureix in self.special_featureixs:
            o.append(
                df.special_features[featureix].description(df, verbose=verbose)
            )
        for trapix in self.trapixs:
            o.append(df.traps[trapix].description())
        o.append(f"Light level: {self.light_level.capitalize()}")
        if verbose:
            if self.encounter:
                o.append(self.encounter.description(df))
            corridorix_doors = {k: None for k in self.corridorixs}
            for doorix in self.doorixs:
                door = df.doors[doorix]
                corridorix_doors[door.corridorix] = door
            for corridorix, door in corridorix_doors.items():
                corridor = df.corridors[corridorix]
                other_roomix = (
                    set([corridor.room1ix, corridor.room2ix]) - set([self.ix])
                ).pop()
                way = "Passage"
                if door:
                    way = door.nickname()
                line = Doc([way], separator=" ")
                other_room = df.rooms[other_roomix]
                if not other_room.is_trivial():
                    line.body.append("to")
                    line.body.append(DocLink(other_room.name()))
                if corridor.is_nontrivial(df):
                    line.body.append("by way of")
                    line.body.append(DocLink(f"Corridor {corridor.name}"))
                door_l = [line]
                if door:
                    for trapix in door.trapixs:
                        door_l.append(df.traps[trapix].description())
                o.append(door_l)
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
        return Doc(DocBookmark(self.name()), o)

    def tts_notecard(self, df):
        obj = tts.reference_object("Reference Notecard")
        doc = self.description(df, verbose=False)
        obj["Nickname"] = doc.flat_header().unstyled()
        obj["Description"] = doc.flat_body().unstyled()
        obj["Transform"]["posY"] = 4.0
        obj["Locked"] = True
        df.tts_xz(self.x, self.y, obj)
        return obj

    def name(self):
        return f"Room {self.name_num}"

    def is_fully_enclosed_by_doors(self):
        return self.doorixs and len(self.doorixs) == len(self.corridorixs)

    def desires_doors(self):
        return NotImplementedError()


class RectRoom(Room):
    def tile_coords(self):
        for x in range(self.x - self.rw, self.x + self.rw + 1):
            for y in range(self.y - self.rh, self.y + self.rh + 1):
                yield (x, y)

    def total_space(self):
        return (1 + self.rw * 2) * (1 + self.rh * 2)

    def desires_doors(self):
        return True


class MazeJunction(RectRoom):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.maze_x = None
        self.maze_y = None

    def is_trivial(self):
        return True

    def desires_doors(self):
        return False

    def allows_treasure(self, df):
        return False

    def allows_bookshelf(self, df):
        return False

    def allows_enemies(self, df):
        return False

    def allows_traps(self, df):
        return False


class CavernousRoom(Room):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.explicit_tile_coords = None

    def tile_style(self):
        return "cavern"

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

    def desires_doors(self):
        return False

    def allows_bookshelf(self, df):
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
                    otile = df.tiles[tx][ty]
                    if isinstance(otile, RoomFloorTile) or isinstance(
                        otile, CorridorFloorTile
                    ):
                        # found another room, oughtn't expand
                        safe_to_expand = False
                        break
            if safe_to_expand:
                erodable.append((x, y))
        for x, y in erodable:
            if random.random() < per_tile_chance:
                self.explicit_tile_coords.append((x, y))
                df.set_tile(self.new_floor_tile(), x=x, y=y)
