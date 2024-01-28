import math
import random


from lib.tile import WaterTile
import lib.tts as tts


class River:
    def __init__(self, diameter, river_tile_coords=None):
        self.diameter = diameter
        self.river_tile_coords = list(river_tile_coords or [])
        self.adjacent_coords_set = self._adjacent_coords()
        self.is_carved = False
        self.ix = None

    def _adjacent_coords(self):
        adjacent_coords = set()
        for x, y in self.river_tile_coords:
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    adjacent_coords.add((x + dx, y + dy))
        for x, y in self.river_tile_coords:
            if (x, y) in adjacent_coords:
                adjacent_coords.remove((x, y))
        return adjacent_coords

    def carve_into_dungeon(self, df):
        adjacent_coords = set()
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
    def propose_river(df, diameter=2):
        start_coords = (
            2 + random.random() * (df.width - 4),
            2 + random.random() * (df.height - 4),
        )
        start_angle = random.random() * math.pi
        river_core_coords = set()
        sin_period = 2 + random.random() * 7
        sin_amplitude = 1.5 * random.random() / sin_period
        sin_offset = random.random() * 2 * math.pi
        jitter_level = random.random() / 5.0

        def step(coords, angle, stepix, d):
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

        coords = start_coords
        angle = start_angle
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
        rlo = -math.floor((diameter - 1) / 2)
        rhi = math.ceil((diameter - 1) / 2) + 1
        river_tile_coords = set()
        for x, y in river_core_coords:
            for dx in range(rlo, rhi):
                for dy in range(rlo, rhi):
                    tx, ty = x + dx, y + dy
                    if tx >= 0 and tx < df.width and ty >= 0 and ty < df.height:
                        river_tile_coords.add((tx, ty))

        return River(diameter=diameter, river_tile_coords=river_tile_coords)

    def tts_fog_bits(self, df):
        """returns a list of fog bits: all small ones probably."""
        fogs = []
        coords = set(self.river_tile_coords).union(self.adjacent_coords_set)
        for x, y in coords:
            tile = df.get_tile(x=x, y=y)
            if tile and (tile.is_water() or tile.blocks_line_of_sight()):
                fogs.append(tts.TTSFogBit(x, y, riverixs=[self.ix]))
        return fogs
