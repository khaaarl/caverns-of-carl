from __future__ import annotations

import math
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import lib.tts as tts
from lib.tile import (
    CorridorFloorTile,
    DoorTile,
    WallTile,
)
from lib.utils import Doc, DocBookmark, DocLink, eval_dice

if TYPE_CHECKING:
    from lib.dungeon import DungeonFloor


class CorridorWalker:
    """Iterator that yields (x, y) coordinates along a corridor's path."""

    def __init__(
        self, corridor: Corridor, max_width_iter: int | None = None
    ) -> None:
        self.corridor: Corridor = corridor
        self.width_iter: int = 0
        self.max_width_iter: int = (
            corridor.width if max_width_iter is None else max_width_iter
        )
        self._initialize()

    def __iter__(self) -> CorridorWalker:
        return self

    def _initialize(self) -> None:
        self.x: int = self.corridor.x1
        self.y: int = self.corridor.y1
        self.x2: int = self.corridor.x2
        self.y2: int = self.corridor.y2
        dx = int(math.copysign(1, self.corridor.x2 - self.corridor.x1))
        dy = int(math.copysign(1, self.corridor.y2 - self.corridor.y1))
        self.going_horizontal: bool = self.corridor.is_horizontal_first
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

    def __next__(self) -> tuple[int, int]:
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
    """An L-shaped passage connecting two rooms, with configurable width."""

    def __init__(
        self,
        room1ix: int,
        room2ix: int,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        is_horizontal_first: bool,
        width: int = 1,
        biome_name: str | None = None,
        force_trivial: bool = False,
    ) -> None:
        self.room1ix: int = room1ix
        self.room2ix: int = room2ix
        self.x1: int = x1
        self.y1: int = y1
        self.x2: int = x2
        self.y2: int = y2
        self.is_horizontal_first: bool = is_horizontal_first
        self.width: int = width
        self.light_level: str = "bright"  # or "dim" or "dark"
        self.ix: int | None = None
        self.doorixs: set[int] = set()
        self.trapixs: set[int] = set()
        self.name: str | None = None
        self.biome_name: str | None = biome_name
        self.force_trivial: bool = force_trivial

    def is_fully_enclosed_by_doors(self) -> bool:
        return len(self.doorixs) >= 2

    def tile_style(self) -> str:
        return "dungeon"

    def walk(self, max_width_iter: int | None = None) -> CorridorWalker:
        return CorridorWalker(self, max_width_iter=max_width_iter)

    def tile_coords(
        self, df: DungeonFloor, include_doors: bool = False
    ) -> Iterator[tuple[int, int]]:
        for x, y in self.walk():
            tile = df.tiles[x][y]
            if isinstance(tile, DoorTile):
                if include_doors:
                    yield (x, y)
                else:
                    continue
            if isinstance(tile, CorridorFloorTile):
                yield (x, y)

    def length(self, df: DungeonFloor) -> int:
        length = 0
        for x, y in self.walk(max_width_iter=1):
            tile = df.tiles[x][y]
            if isinstance(tile, CorridorFloorTile):
                length += 1
        return length

    def is_trivial(self, df: DungeonFloor) -> bool:
        return not self.is_nontrivial(df)

    def is_nontrivial(self, df: DungeonFloor) -> bool:
        if self.force_trivial:
            return False
        usable_length = 0.0
        for x, y in self.walk():
            tile = df.tiles[x][y]
            if isinstance(tile, CorridorFloorTile) and not isinstance(
                tile, DoorTile
            ):
                usable_length += 1.0 / self.width
        return usable_length > 2.5

    def description(self, df: DungeonFloor, verbose: bool = False) -> Doc:
        o: list[Any] = []
        for trapix in self.trapixs:
            o.append(df.traps[trapix].description())
        o.append(f"Light level: {self.light_level.capitalize()}")
        if verbose:
            roomix_doors: dict[int, Door | None] = {
                self.room1ix: None,
                self.room2ix: None,
            }
            for doorix in self.doorixs:
                door = df.doors[doorix]
                assert len(door.roomixs) == 1
                roomix_doors[list(door.roomixs)[0]] = door
            for roomix, door in roomix_doors.items():
                way = "Passage"
                if door:
                    way = door.nickname()
                line = Doc([way], separator=" ")
                room = df.rooms[roomix]
                if not room.is_trivial():
                    line.body.append("to")
                    line.body.append(DocLink(room.name()))
                door_l: list[Any] = [line]
                if door:
                    for trapix in door.trapixs:
                        door_l.append(df.traps[trapix].description())
                o.append(door_l)
        name = f"Corridor {self.name}"
        return Doc(DocBookmark(name, name), o)

    def tts_notecard(self, df: DungeonFloor) -> dict[str, Any]:
        obj = tts.reference_object("Reference Notecard")
        doc = self.description(df)
        obj["Nickname"] = doc.flat_header().unstyled()
        obj["Description"] = doc.flat_body(separator="\n\n").unstyled()
        obj["Transform"]["posY"] = 4.0
        obj["Locked"] = True
        x, y = self.middle_coords(df)
        df.tts_xz(x, y, obj)
        return obj

    def middle_coords(self, df: DungeonFloor) -> tuple[int, int]:
        """
        Attempts to find the midpoint(ish) of the corridor's tunnel.
        Returns a pair (x, y) of that point's coordinates.
        Raises RuntimeError in pathological cases (corridors which did not go through walls; won't happen in practice).
        """
        in_corridor = False
        corridor_coords: list[tuple[int, int]] = []
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

    def door_coords(self, df: DungeonFloor) -> list[tuple[int, int]]:
        """
        Returns a list of pairs (x, y) of coordinates of the
        corridor's doors. This only produces one result for a
        double/triple wide door; if the caller needs those tiles,
        should examine nearby tiles.
        """
        in_corridor = False
        door_coords: list[tuple[int, int]] = []
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

    def tts_fog_bits(self, df: DungeonFloor) -> list[tts.TTSFogBit]:
        """returns a list of fog bits: all small ones probably."""
        fogs: list[tts.TTSFogBit] = []
        num_blank_corridor_tiles = 0
        # walked places
        for x, y in self.walk():
            tile = df.tiles[x][y]
            if isinstance(tile, CorridorFloorTile) and not tile.riverixs:
                if not isinstance(tile, DoorTile):
                    num_blank_corridor_tiles += 1
                fogs.append(tts.TTSFogBit(x, y, corridorixs=[self.ix]))
                for nt in df.neighbor_tiles(x, y, diagonal=True):
                    if isinstance(nt, WallTile):
                        fogs.append(
                            tts.TTSFogBit(nt.x, nt.y, corridorixs=[self.ix])
                        )
        if num_blank_corridor_tiles == 0:
            return []
        return fogs


class CavernousCorridor(Corridor):
    """Corridor with cavern styling; never has doors."""

    def is_fully_enclosed_by_doors(self) -> bool:
        return False

    def tile_style(self) -> str:
        return "cavern"


class Door:
    """A door placed at a corridor-room boundary, with type, lock, and secret status."""

    def __init__(
        self,
        door_type: str,
        corridor: Corridor,
        x: int,
        y: int,
        roomixs: list[int] | None = None,
        lock_dc: int | None = None,
        biome_name: str | None = None,
        is_secret: bool = False,
        detection_dc: int | None = None,
    ) -> None:
        self.door_type: str = door_type
        self.x: int = x
        self.y: int = y
        self.corridorix: int | None = corridor.ix
        self.width: int = corridor.width
        self.roomixs: set[int] = set(roomixs or [])
        self.trapixs: set[int] = set()
        self.ix: int | None = None
        self.lock_dc: int | None = lock_dc
        self.biome_name: str | None = biome_name
        self.is_secret: bool = is_secret
        self.detection_dc: int | None = detection_dc

    def apply_minimum_door_strength(self, min_door_type: str) -> None:
        min_row_ix = 0
        cur_row_ix = 0
        for rowix, row in enumerate(Door.door_type_table):
            if row[0] == min_door_type:
                min_row_ix = rowix
            if row[0] == self.door_type:
                cur_row_ix = rowix
        if cur_row_ix < min_row_ix:
            self.door_type = Door.door_type_table[min_row_ix][0]

    def thickness(self) -> int:
        return Door.door_type_dict[self.door_type]["thickness"]

    def damage_threshold(self) -> int:
        return Door.door_type_dict[self.door_type]["threshold"]

    def armor_class(self) -> int:
        return Door.door_type_dict[self.door_type]["ac"]

    def health(self) -> int:
        return Door.door_type_dict[self.door_type]["hp"]

    def nickname(self) -> str:
        nick = ""
        if self.is_secret:
            nick += "Secret "
        if self.lock_dc is not None:
            nick += "Locked "
        size_prefix = {1: "Small", 2: "Large", 3: "Huge"}[self.width]
        nick += f"{size_prefix} {self.door_type}"
        return nick

    def tts_nickname(self) -> str:
        if self.is_secret:
            return ""
        nick = f"{self.health()}/{self.health()} "
        return nick + self.nickname()

    def tts_description(self) -> str:
        if self.is_secret:
            return ""
        return "\n".join(
            [
                f"Armor Class: {self.armor_class()}",
                f"Damage Threshold: {self.damage_threshold()}",
            ]
        )

    def tts_gmnotes(self, df: DungeonFloor) -> str:
        output: list[str] = []
        if self.is_secret:
            output.append(f"Secret Door! Detection DC: {self.detection_dc}")
        if self.lock_dc is not None:
            output.append(f"Lock DC: {self.lock_dc}")
        if self.trapixs:
            for trapix in self.trapixs:
                trap = df.traps[trapix]
                output.append(trap.description())
        return "\n".join(output)

    # name, thickness, damage threshold, armor class, hit points
    door_type_table: list[tuple[str, int, int, int, int]] = [
        ("Crude Wooden Door", 1, 0, 15, 10),
        ("Simple Wooden Door", 2, 0, 15, 15),
        ("Heavy Wooden Door", 4, 10, 15, 25),
        ("Reinforced Wooden Door", 4, 15, 17, 40),
        ("Stone Door", 4, 25, 17, 60),
        ("Iron Door", 2, 30, 19, 100),
    ]
    door_type_dict: dict[str, dict[str, Any]] = {
        t[0]: {
            "name": t[0],
            "thickness": t[1],
            "threshold": t[2],
            "ac": t[3],
            "hp": t[4],
        }
        for t in door_type_table
    }

    @staticmethod
    def pick_type(config: Any) -> str:
        """Randomly select a door type scaled to the party's level."""
        lvl = config.target_character_level - 5 + eval_dice("1d20")
        max_ix = len(Door.door_type_table) - 1
        ix = min(int(lvl * max_ix / 30.0), max_ix)
        t = Door.door_type_table[ix]
        return t[0]
