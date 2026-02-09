from __future__ import annotations

import math
import random
from collections.abc import Iterable
from typing import TYPE_CHECKING

import lib.tts as tts
from lib.tile import WaterTile

if TYPE_CHECKING:
    from lib.dungeon import DungeonFloor


class River:
    """A sinusoidal river that carves water tiles across the dungeon."""

    def __init__(
        self,
        diameter: int,
        river_tile_coords: Iterable[tuple[int, int]] | None = None,
    ) -> None:
        self.diameter: int = diameter
        self.river_tile_coords: list[tuple[int, int]] = list(
            river_tile_coords or []
        )
        self.adjacent_coords_set: set[tuple[int, int]] = (
            self._adjacent_coords()
        )
        self.is_carved: bool = False
        self.ix: int | None = None

    def _adjacent_coords(self) -> set[tuple[int, int]]:
        adjacent_coords: set[tuple[int, int]] = set()
        for x, y in self.river_tile_coords:
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    adjacent_coords.add((x + dx, y + dy))
        for x, y in self.river_tile_coords:
            if (x, y) in adjacent_coords:
                adjacent_coords.remove((x, y))
        return adjacent_coords

    def carve_into_dungeon(self, df: DungeonFloor) -> None:
        """Replace tiles along the river's path with WaterTiles."""
        adjacent_coords: set[tuple[int, int]] = set()
        for x, y in self.river_tile_coords:
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    adjacent_coords.add((x + dx, y + dy))
        for x, y in self.river_tile_coords:
            if (x, y) in adjacent_coords:
                adjacent_coords.remove((x, y))
            old_tile = df.get_tile(x=x, y=y)
            tile = WaterTile(x=old_tile.x, y=old_tile.y)
            tile.biome_name = old_tile.biome_name
            tile.roomix = old_tile.roomix
            tile.corridorix = old_tile.corridorix
            tile.light_level = old_tile.light_level
            tile.riverixs = set(old_tile.riverixs)
            tile.riverixs.add(self.ix)
            df.set_tile(tile)

    @staticmethod
    def propose_river(df: DungeonFloor, diameter: int = 2) -> River:
        """Generate a random sinusoidal river path across the dungeon."""
        start_coords: tuple[float, float] = (
            2 + random.random() * (df.width - 4),
            2 + random.random() * (df.height - 4),
        )
        start_angle: float = random.random() * math.pi
        river_core_coords: set[tuple[int, int]] = set()
        sin_period: float = 2 + random.random() * 7
        sin_amplitude: float = 1.5 * random.random() / sin_period
        sin_offset: float = random.random() * 2 * math.pi
        jitter_level: float = random.random() / 5.0

        def step(
            coords: tuple[float, float],
            angle: float,
            stepix: int,
            d: float,
        ) -> tuple[tuple[float, float], float, bool]:
            angle += (random.random() - 0.5) * jitter_level * d
            angle += (
                sin_amplitude
                * math.sin(sin_offset + (stepix * d) / sin_period)
                * d
            )
            coords = (
                coords[0] + d * math.cos(angle),
                coords[1] + d * math.sin(angle),
            )
            river_core_coords.add((int(coords[0]), int(coords[1])))
            done = (
                coords[0] + diameter + 1 < 0
                or coords[0] - diameter - 1 > df.width
                or coords[1] + diameter + 1 < 0
                or coords[1] - diameter - 1 > df.height
            )
            return (coords, angle, done)

        coords: tuple[float, float] = start_coords
        angle: float = start_angle
        for ix in range(10000):
            coords, angle, done = step(coords, angle, ix, 0.1)
            if done:
                break
        coords = start_coords
        angle = start_angle
        for ix in range(1, 10000):
            coords, angle, done = step(coords, angle, ix, -0.1)
            if done:
                break
        rlo: int = -math.floor((diameter - 1) / 2)
        rhi: int = math.ceil((diameter - 1) / 2) + 1
        river_tile_coords: set[tuple[int, int]] = set()
        for x, y in river_core_coords:
            for dx in range(rlo, rhi):
                for dy in range(rlo, rhi):
                    tx, ty = x + dx, y + dy
                    if (
                        tx >= 0
                        and tx < df.width
                        and ty >= 0
                        and ty < df.height
                    ):
                        river_tile_coords.add((tx, ty))

        return River(diameter=diameter, river_tile_coords=river_tile_coords)

    def tts_fog_bits(self, df: DungeonFloor) -> list[tts.TTSFogBit]:
        """returns a list of fog bits: all small ones probably."""
        fogs: list[tts.TTSFogBit] = []
        coords = set(self.river_tile_coords).union(self.adjacent_coords_set)
        for x, y in coords:
            tile = df.get_tile(x=x, y=y)
            if tile and (tile.is_water() or tile.blocks_line_of_sight()):
                fogs.append(tts.TTSFogBit(x, y, riverixs=[self.ix]))
        return fogs
