import random
import re

import lib.treasure as treasure
import lib.tts as tts


class Tile:
    def __init__(self, x=None, y=None, biome_name=None):
        self.x = x
        self.y = y
        self.tile_style = None
        self.roomix = None
        self.corridorix = None
        self.doorix = None
        self.riverixs = set()
        self.trapixs = set()
        self.light_level = "bright"  # or "dim" or "dark"
        self.is_interior = False
        self.biome_name = biome_name

    def _tts_light_mul(self, obj):
        ref = tts.reference_object("Floor, Dungeon")
        mesh_url = obj.get("CustomMesh", {}).get("MeshURL")
        if mesh_url == ref["CustomMesh"]["MeshURL"]:
            mul = 1.0
            if self.light_level == "dim":
                mul = 0.7
            elif self.light_level == "dark":
                mul = 0.3
            obj["ColorDiffuse"] = {k: mul for k in "rgb"}
        for other in obj.get("States", {}).values():
            self._tts_light_mul(other)
        for other in obj.get("ChildObjects", []):
            self._tts_light_mul(other)

    def to_char(self):
        return "?"

    def is_move_blocking(self):
        return True

    def is_feature(self):
        return False

    def is_ladder(self):
        return False

    def is_chest(self):
        return False

    def is_water(self):
        return False

    def is_wall(self):
        return False

    def blocks_line_of_sight(self):
        return False

    def _alter_tex(self, obj, ref, new):
        mesh_url = obj.get("CustomMesh", {}).get("MeshURL")
        if mesh_url == ref["CustomMesh"]["MeshURL"]:
            assert mesh_url == new["CustomMesh"]["MeshURL"]
            obj["CustomMesh"]["DiffuseURL"] = new["CustomMesh"]["DiffuseURL"]
            obj["CustomMesh"]["NormalURL"] = new["CustomMesh"]["NormalURL"]
        for other in obj.get("States", {}).values():
            self._alter_tex(other, ref, new)
        for other in obj.get("ChildObjects", []):
            self._alter_tex(other, ref, new)

    def _update_texture_style(self, obj, df):
        tile_style = self.tile_style
        if not tile_style and self.roomix is not None:
            tile_style = df.rooms[self.roomix].tile_style()
        if not tile_style and self.corridorix is not None:
            tile_style = df.corridors[self.corridorix].tile_style()
        new_floor = None
        if tile_style == "cavern":
            new_floor = tts.reference_object("Floor, Cavern")
        if new_floor:
            ref_floor = tts.reference_object("Floor, Dungeon")
            self._alter_tex(obj, ref_floor, new_floor)

    def _update_tile_for_features(self, obj, df):
        if self.roomix is None:
            return
        room = df.rooms[self.roomix]
        for featureix in room.special_featureixs:
            feature = df.special_features[featureix]
            feature.mod_tts_room_tile(obj)

    def _tts_gmnotes(self, df):
        output = []
        if isinstance(self, MimicTile):
            output.append("Mimic!")
        if self.doorix is not None:
            door = df.doors[self.doorix]
            output.append(door.tts_gmnotes(df))
        elif self.roomix is not None:
            room = df.rooms[self.roomix]
            doc = room.description(df, verbose=False)
            output.append(doc.flat_header().unstyled())
        elif self.corridorix is not None:
            corridor = df.corridors[self.corridorix]
            doc = corridor.description(df, verbose=False)
            output.append(doc.flat_header().unstyled())
        for trapix in self.trapixs:
            trap = df.traps[trapix]
            output.append(trap.description())
        return "\n".join(output)

    def _postprocess_tts_object(self, obj, df):
        self._update_texture_style(obj, df)
        self._tts_light_mul(obj)
        self._update_tile_for_features(obj, df)
        obj["GMNotes"] = self._tts_gmnotes(df)


class WallTile(Tile):
    def is_wall(self):
        return True

    def blocks_line_of_sight(self):
        return True

    def to_char(self):
        if self.is_interior:
            return " "
        if self.tile_style == "cavern":
            return "[0;33m#"
        return "[0;37m#"

    def tts_objects(self, df):
        if self.tile_style == "cavern":
            # use different wall bits if different adjacent walls
            def is_neighbor_wall(dx, dy):
                tx, ty = self.x + dx, self.y + dy
                return isinstance(df.get_tile(tx, ty, WallTile), WallTile)

            num_diagonal_neighbors = sum(
                [is_neighbor_wall(dx, dy) for dx in [-1, 1] for dy in [-1, 1]]
            )
            west = is_neighbor_wall(-1, 0)
            east = is_neighbor_wall(1, 0)
            north = is_neighbor_wall(0, 1)
            south = is_neighbor_wall(0, -1)
            num_neighbors = sum([west, east, north, south])
            rand = random.random()
            if num_neighbors == 0:
                obj = tts.reference_object("Cavern Stalagmite Column")
                obj["Transform"]["rotY"] = 90.0 * random.randrange(4)
            elif num_neighbors == 1:
                obj = tts.reference_object("Cavern Wall 1 Connection")
                if east:
                    obj["Transform"]["rotY"] = 180.0
                elif north:
                    obj["Transform"]["rotY"] = 90.0
                elif south:
                    obj["Transform"]["rotY"] = 270.0
                else:
                    obj["Transform"]["rotY"] = 0.0
            elif num_neighbors == 2 and rand < 0.7:
                if west and east:
                    obj = tts.reference_object(
                        "Cavern Wall 2 Connections Through"
                    )
                    obj["Transform"]["rotY"] = 0.0 + 180.0 * random.randrange(2)
                elif north and south:
                    obj = tts.reference_object(
                        "Cavern Wall 2 Connections Through"
                    )
                    obj["Transform"]["rotY"] = 90.0 + 180.0 * random.randrange(
                        2
                    )
                else:
                    obj = tts.reference_object(
                        "Cavern Wall 2 Connections Corner"
                    )
                    if east and south:
                        obj["Transform"]["rotY"] = 0.0
                    if west and south:
                        obj["Transform"]["rotY"] = 90.0
                    if west and north:
                        obj["Transform"]["rotY"] = 180.0
                    if east and north:
                        obj["Transform"]["rotY"] = 270.0
            elif num_neighbors == 3 and (
                rand < 0.1 or num_diagonal_neighbors >= 3 and rand < 0.8
            ):
                obj = tts.reference_object("Cavern Wall 3 Connections")
                if not west:
                    obj["Transform"]["rotY"] = 0.0
                if not north:
                    obj["Transform"]["rotY"] = 90.0
                if not east:
                    obj["Transform"]["rotY"] = 180.0
                if not south:
                    obj["Transform"]["rotY"] = 270.0
            else:
                obj = tts.reference_object("Cavern Wall Ambiguous Connections")
                obj["Transform"]["rotY"] = 90.0 * random.randrange(4)
        else:
            obj = tts.reference_object("Wall, Dungeon")
            obj["Transform"]["rotY"] = 90.0 * random.randrange(4)
        obj["Nickname"] = ""
        self._postprocess_tts_object(obj, df)
        return [obj]


class FloorTile(Tile):
    def tts_objects(self, df):
        obj = tts.reference_object("Floor, Dungeon")
        obj["Transform"]["rotY"] = 90.0 * random.randrange(4)
        obj["Nickname"] = ""
        self._postprocess_tts_object(obj, df)
        return [obj]

    def is_move_blocking(self):
        return False


class RoomFloorTile(FloorTile):
    def __init__(self, roomix, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.roomix = roomix

    def to_char(self):
        if self.tile_style == "cavern":
            return "[0;33m."
        return "[0;37m."


class CorridorFloorTile(FloorTile):
    def __init__(self, corridorix, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.corridorix = corridorix

    def to_char(self):
        if self.tile_style == "cavern":
            return "[0;33m,"
        return "[0;37m,"


class DoorTile(CorridorFloorTile):
    def __init__(self, corridorix, doorix=None, *args, **kwargs):
        super().__init__(corridorix, *args, **kwargs)
        self.doorix = doorix

    def to_char(self):
        return "+"

    def blocks_line_of_sight(self):
        return True

    def tts_objects(self, df):
        obj = None
        corridor = df.corridors[self.corridorix]
        if corridor.width == 1:
            obj = tts.reference_object("Door, Metal")
        elif corridor.width == 2:
            if isinstance(df.tiles[self.x + 1][self.y], DoorTile) or isinstance(
                df.tiles[self.x][self.y - 1], DoorTile
            ):
                obj = tts.reference_object("Door, Double")
        else:
            if (
                isinstance(df.tiles[self.x + 1][self.y], DoorTile)
                and isinstance(df.tiles[self.x - 1][self.y], DoorTile)
                or isinstance(df.tiles[self.x][self.y + 1], DoorTile)
                and isinstance(df.tiles[self.x][self.y - 1], DoorTile)
            ):
                obj = tts.reference_object("Door, Triple")
        if obj:
            for dx in [1, -1]:
                if isinstance(df.tiles[self.x + dx][self.y], RoomFloorTile):
                    obj["Transform"]["rotY"] = 90.0
            door = df.doors[self.doorix]
            obj["Nickname"] = door.tts_nickname()
            obj["Description"] = door.tts_description()
            self._postprocess_tts_object(obj, df)
            return [obj]
        return []

    def is_move_blocking(self):
        return True


class LadderUpTile(RoomFloorTile):
    def to_char(self):
        return "[1;97m<"

    def tts_objects(self, df):
        obj = tts.reference_object("Ladder, Wood")
        # TODO: adjust such that ladder is against the wall if a wall is near
        obj["Transform"]["rotY"] = 90.0 * random.randrange(4)
        obj["Nickname"] = "Ladder up"
        self._postprocess_tts_object(obj, df)
        return [obj]

    def is_move_blocking(self):
        return True

    def is_ladder(self):
        return True


class LadderDownTile(RoomFloorTile):
    def to_char(self):
        return "[1;97m>"

    def tts_objects(self, df):
        obj = tts.reference_object("Floor, Hatch")
        obj["Transform"]["rotY"] = 90.0 * random.randrange(4)
        obj["Nickname"] = "Hatch down"
        self._postprocess_tts_object(obj, df)
        return [obj]

    def is_move_blocking(self):
        return True

    def is_ladder(self):
        return True


def rotY_away_from_wall(df, x, y, original=0):
    posrots = [(0, 1, 0), (1, 0, 90), (0, -1, 180), (-1, 0, 270)]
    random.shuffle(posrots)
    for dx, dy, r in posrots:
        if isinstance(df.tiles[x + dx][y + dy], WallTile):
            return original + r
    return None


class ChestTile(RoomFloorTile):
    def __init__(self, roomix, contents="", *args, **kwargs):
        super().__init__(roomix, *args, **kwargs)
        self.contents = contents

    def to_char(self):
        return "[1;93m$"

    def tts_objects(self, df):
        obj = tts.reference_object("Chest Closed Tile")
        obj["Transform"]["rotY"] += rotY_away_from_wall(df, self.x, self.y)
        obj["Nickname"] = "Chest"
        opened = obj["States"]["2"]
        opened["Nickname"] = "Open Chest"
        if self.contents:
            opened["Description"] = "Contents:\n" + self.contents
            opened["ContainedObjects"] = self.tts_contained_objects()
        self._postprocess_tts_object(obj, df)
        return [obj]

    def is_move_blocking(self):
        return True

    def is_feature(self):
        return True

    def is_chest(self):
        return True

    def tts_contained_objects(self):
        if self.contents == "Nothing!":
            return []
        return [
            self.tts_object_from_one_contents(line)
            for line in self.contents.split("\n")
        ]

    def tts_object_from_one_contents(self, line):
        SCROLL_RE = r"^[sS]pell [sS]croll \((\d.. [lL]evel|cantrip)\).*$"
        BOOK_RE = r"^[bB]ook: (.+)$"
        GEM_RE = r"^Gemstone \((\d+) gp\): (.*)$"
        tts_reference_name = None
        nickname = None
        description = None
        m = re.match(BOOK_RE, line)
        if m:
            title = m.groups()[0].strip()
            book = treasure.book_library()[title]
            return book.tts_object()
        if re.match("^Scroll of Protection", line):
            tts_reference_name = "Reference Scroll Low"
        m = re.match(SCROLL_RE, line)
        if m:
            if m.groups()[0] == "cantrip":
                scroll_level = 0
            else:
                scroll_level = int(m.groups()[0][0])
            if scroll_level < 3:
                tts_reference_name = "Reference Scroll Low"
            elif scroll_level < 6:
                tts_reference_name = "Reference Scroll Medium"
            else:
                tts_reference_name = "Reference Scroll High"
        m = re.match(GEM_RE, line)
        if m:
            gp, gem = m.groups()
            tts_reference_name = f"{gem.strip().title()} ({int(gp):,}gp)"
        try:
            item = tts.reference_object(tts_reference_name or line)
        except KeyError:
            item = tts.reference_object("Unknown Object Token")
        item["Nickname"] = nickname or line
        if description:
            item["Description"] = description
        return item


class BookshelfTile(ChestTile):
    def is_move_blocking(self):
        return False

    def to_char(self):
        return "[1;93mB"

    def tts_objects(self, df):
        obj = tts.reference_object("Bookshelf Tile")
        obj["Transform"]["rotY"] += rotY_away_from_wall(df, self.x, self.y)
        obj["Nickname"] = "Bookshelf"
        opened = obj["States"]["2"]
        opened["Nickname"] = "Examined Bookshelf"
        if self.contents:
            opened = obj["States"]["2"]
            opened["Description"] = "Contents:\n" + self.contents
            opened["ContainedObjects"] = self.tts_contained_objects()
        self._postprocess_tts_object(obj, df)
        return [obj]


class MimicTile(ChestTile):
    def __init__(self, roomix, monster, *args, **kwargs):
        super().__init__(roomix, contents="", *args, **kwargs)
        self.monster = monster

    def to_char(self):
        return "m"

    def tts_objects(self, df):
        obj = tts.reference_object("Chest Closed Mimic Tile")
        obj["Transform"]["rotY"] += rotY_away_from_wall(df, self.x, self.y)
        obj["Nickname"] = "Chest"
        obj["States"]["2"]["Nickname"] = "It's a Mimic!"
        obj["States"]["2"]["ChildObjects"][0][
            "Nickname"
        ] = self.monster.tts_nickname()
        self._postprocess_tts_object(obj, df)
        return [obj]


class WaterTile(Tile):
    def is_water(self):
        return True

    def to_char(self):
        return "[1;94m~"

    def tts_objects(self, df):
        refs = ["River Tile A"] * 8 + ["River Tile B", "River Tile C"]
        obj = tts.reference_object(random.choice(refs))
        obj["Transform"]["rotY"] = random.randrange(4) * 90.0
        obj["Nickname"] = ""
        obj["Description"] = ""
        self._postprocess_tts_object(obj, df)
        return [obj]
