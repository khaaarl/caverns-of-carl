import collections
import math
import random

import lib.config
from lib.corridors import Corridor, CavernousCorridor, Door
import lib.lights
import lib.monster
from lib.monster import get_monster_library, Monster
import lib.npcs
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
from lib.room import Room, RectRoom, CavernousRoom, MazeJunction
import lib.features
import lib.trap
from lib.treasure import get_treasure_library
from lib.utils import (
    bfs,
    choice,
    dfs,
    eval_dice,
    neighbor_coords,
    random_dc,
    samples,
)


class RetriableDungeonographyException(Exception):
    pass


class RetriableRoomPlacementException(RetriableDungeonographyException):
    pass


class RetriableCorridorPlacementException(RetriableDungeonographyException):
    pass


class RetriableFeaturePlacementException(RetriableDungeonographyException):
    pass


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
        self.npcs = []
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
        x = random.randrange(2, self.width - 3)
        y = random.randrange(2, self.height - 3)
        tile = self.tiles[x][y]
        biome = self.config.get_biome(tile.biome_name)
        r = int(max(1, biome.min_room_radius))
        x = min(max(1 + r, x), self.width - 2 - r)
        y = min(max(1 + r, y), self.height - 2 - r)
        cls = RectRoom
        if random.random() * 100.0 < biome.cavernous_room_percent:
            cls = CavernousRoom
        return cls(x=x, y=y, rw=r, rh=r, biome_name=tile.biome_name)

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

    def get_tiles(self):
        l = []
        for x in range(self.width):
            for y in range(self.height):
                l.append(self.tiles[x][y])
        return l

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
        self.rooms[corridor.room1ix].corridorixs.add(corridor.ix)
        self.rooms[corridor.room2ix].corridorixs.add(corridor.ix)
        self.room_neighbors[corridor.room1ix].add(corridor.room2ix)
        self.room_neighbors[corridor.room2ix].add(corridor.room1ix)
        for x, y in corridor.walk():
            if isinstance(self.tiles[x][y], WallTile):
                self.set_tile(
                    CorridorFloorTile(
                        corridor.ix, biome_name=corridor.biome_name
                    ),
                    x=x,
                    y=y,
                )

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
        if ix_to_ignore is not None and ix == ix_to_ignore:
            continue
        if (abs(room.x - r2.x) <= room.rw + r2.rw + 1) and (
            abs(room.y - r2.y) <= room.rh + r2.rh + 1
        ):
            return False
    for x in range(room.x - room.rw - 1, room.x + room.rw + 2):
        for y in range(room.y - room.rh - 1, room.y + room.rh + 2):
            if not isinstance(df.get_tile(x, y), WallTile):
                return False
    return True


def generate_random_dungeon(config=None, errors=None):
    config = config or lib.config.DungeonConfig()
    errors = errors or []
    successful = False
    for _ in range(100):
        try:
            df = DungeonFloor(config)
            place_biomes_in_dungeon(df)
            place_mazes_in_dungeon(df)
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
            add_npcs_to_dungeon(df)
        except RetriableDungeonographyException as err:
            errors.append(err)
        else:
            successful = True
        if successful:
            break
    if successful:
        return df
    raise errors[-1]


def place_biomes_in_dungeon(df):
    for tile in df.get_tiles():
        biome_weight_names = []
        for biome in df.config.biomes:
            weight = 0.0
            weight += (tile.y / df.height) * biome.biome_northness
            weight += (1 - tile.y / df.height) * biome.biome_southness
            weight += (tile.x / df.width) * biome.biome_eastness
            weight += (1 - tile.x / df.width) * biome.biome_westness
            weight += random.random()
            biome_weight_names.append((weight, biome.biome_name))
        if len(df.config.biomes) < 2:
            biome_weight_names.append((3.0 + random.random(), None))
        tile.biome_name = sorted(biome_weight_names)[-1][1]


def place_mazes_in_dungeon(df):
    for biome in df.config.biomes + [df.config]:
        if biome.use_maze_layout:
            place_maze_in_biome(df, biome)


def place_maze_in_biome(df, biome):
    maze_corridor_width = 3
    maze_width = int((df.width + 1) / (maze_corridor_width * 2))
    maze_height = int((df.height + 1) / (maze_corridor_width * 2))
    maze_offset = 2

    def maze_xy_to_tile(mx, my):
        x = maze_offset + mx * 2 * maze_corridor_width
        y = maze_offset + my * 2 * maze_corridor_width
        return df.get_tile(x=x, y=y)

    maze_grid = [[None for _ in range(maze_height)] for _ in range(maze_width)]
    not_us_junctions = 0
    junctions = []
    junctions_by_mxy = collections.defaultdict(lambda: None)
    for mx in range(maze_width):
        for my in range(maze_height):
            tile = maze_xy_to_tile(mx, my)
            if tile.biome_name != biome.biome_name:
                not_us_junctions += 1
                continue
            junction = MazeJunction(tile.x, tile.y, biome_name=biome.biome_name)
            junction.maze_x = mx
            junction.maze_y = my
            junctions.append(junction)
            junctions_by_mxy[(mx, my)] = junction
            maze_grid[mx][my] = junction
    if not junctions:
        return
    connections = collections.defaultdict(set)
    for junction in junctions:
        for dmx, dmy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            x, y = junction.maze_x, junction.maze_y
            nmx, nmy = x + dmx, y + dmy
            if junctions_by_mxy[(nmx, nmy)]:
                connections[(x, y)].add((nmx, nmy))
                connections[(nmx, nmy)].add((x, y))

    # The sections of the grid aren't guaranteed to be contiguous.
    # Prune until it is.
    mxmy_to_remove = set()
    while True:
        keys = list(connections.keys())
        if not keys:
            return
        p = keys[0]
        if len(dfs(connections, p)) == len(junctions) - len(mxmy_to_remove):
            break
        keys.sort(key=lambda p: len(dfs(connections, p)))
        p = keys[0]
        mxmy_to_remove.add(p)
        del connections[p]
        for k, v in connections.items():
            if p in v:
                v.remove(p)
    for p in mxmy_to_remove:
        maze_grid[p[0]][p[1]] = None
    junctions = []
    for mx in range(maze_width):
        for my in range(maze_height):
            if maze_grid[mx][my]:
                junctions.append(maze_grid[mx][my])

    # Replace some junctions with regular rooms
    target_num_rooms = int(
        round(df.config.num_rooms * len(junctions) / (maze_width * maze_height))
    )
    random.shuffle(junctions)
    room_ps = []
    for junction in junctions[:target_num_rooms]:
        room = RectRoom(
            x=junction.x, y=junction.y, rw=1, rh=1, biome_name=biome.biome_name
        )
        mx, my = junction.maze_x, junction.maze_y
        if mx > 0 and mx < maze_width - 1:
            if isinstance(maze_grid[mx - 1][my], RectRoom) or isinstance(
                maze_grid[mx + 1][my], RectRoom
            ):
                room.rw += 1
            else:
                room.rw += 2
        if my > 0 and my < maze_height - 1:
            if isinstance(maze_grid[mx][my - 1], RectRoom) or isinstance(
                maze_grid[mx][my + 1], RectRoom
            ):
                room.rh += 1
            else:
                room.rh += 2
        room_ps.append((mx, my))
        maze_grid[mx][my] = room
    for l in maze_grid:
        for item in l:
            if isinstance(item, Room):
                item.in_maze = True
                df.add_room(item)

    # DFS-based algorithm for connecting the maze
    start = random.choice(list(connections.keys()))
    dfs_path = dfs(connections, start, include_previous=True, randomize=True)
    connections = collections.defaultdict(set)
    for a, b in dfs_path[1:]:
        connections[a].add(b)
        connections[b].add(a)

    # dig the corridors determined by the above algorithm
    for p1 in list(connections.keys()):
        others = list(connections[p1])
        for p2 in others:
            if p1 > p2:
                continue
            room1 = maze_grid[p1[0]][p1[1]]
            room2 = maze_grid[p2[0]][p2[1]]
            corridor = carve_corridor(
                df,
                room1,
                room2,
                maze_corridor_width,
                True,
                biome.biome_name,
                force_trivial=True,
            )
            df.add_corridor(corridor)


def place_rooms_in_dungeon(df):
    num_rooms_already = 0
    for room in df.rooms:
        if not room.is_trivial():
            num_rooms_already += 1
    config = df.config
    rooms = []
    num_attempts = 0
    while len(rooms) + num_rooms_already < config.num_rooms:
        if num_attempts > config.max_room_attempts * config.num_rooms:
            raise RetriableRoomPlacementException(
                f"Failed to place all requested rooms ({len(rooms)+num_rooms_already} of {config.num_rooms})"
            )
        num_attempts += 1
        room = df.random_room()
        biome = df.config.get_biome(room.biome_name)
        if biome.use_maze_layout:
            continue
        if is_room_valid(room, df, rooms + df.rooms):
            rooms.append(room)
        elif len(rooms) > 0:
            # wiggle something a bit just in case this helps
            ix = random.randrange(0, len(rooms))
            room2 = rooms[ix].wiggled()
            if is_room_valid(room2, df, rooms + df.rooms, ix):
                rooms[ix] = room2

    # embiggen and wiggle rooms
    ews = ["e"] * config.num_room_embiggenings * len(rooms) + [
        "w"
    ] * config.num_room_wiggles * len(rooms)
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
    # sort rooms from top to bottom so their indices are more human comprehensible maybe
    rooms.sort(key=lambda r: (-r.y, r.x))
    # add rooms to dungeon floor
    for room in rooms:
        df.add_room(room)
    # apply light levels
    for room in df.rooms:
        biome = df.config.get_biome(room.biome_name)
        room.light_level = choice(
            ["bright", "dim", "dark"],
            weights=[
                biome.room_bright_ratio,
                biome.room_dim_ratio,
                biome.room_dark_ratio,
            ],
        )


def erode_cavernous_rooms_in_dungeon(df):
    for room in df.rooms:
        if isinstance(room, CavernousRoom):
            room.erode(df, num_iterations=df.config.num_erosion_steps)


def carve_corridor(
    df,
    room1,
    room2,
    width,
    is_horizontal_first,
    biome_name,
    force_trivial=False,
):
    cls = Corridor
    if isinstance(room1, CavernousRoom) and isinstance(room2, CavernousRoom):
        cls = CavernousCorridor
    corridor = cls(
        room1.ix,
        room2.ix,
        room1.x,
        room1.y,
        room2.x,
        room2.y,
        is_horizontal_first,
        width=width,
        biome_name=biome_name,
        force_trivial=force_trivial,
    )
    wall_entries = 0
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
        if not df.config.allow_corridor_intersection and isinstance(
            tile, CorridorFloorTile
        ):
            return None
        if not isinstance(tile, RoomFloorTile):
            if isinstance(ptile, RoomFloorTile):
                wall_entries += 1
                if wall_entries > 1:
                    return None
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
                    return None
    # set light level to in between the two rooms
    light_levels = sorted([room1.light_level, room2.light_level])
    corridor.light_level = random.choice(light_levels)
    if light_levels == ["bright", "dark"]:
        corridor.light_level = "dim"
    return corridor


def place_corridors_in_dungeon(df):
    config = df.config
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
        if room2ix in df.room_neighbors[room1ix]:
            continue
        is_horizontal_first = random.randrange(2)

        room1 = df.rooms[room1ix]
        room2 = df.rooms[room2ix]
        biome_name = room1.biome_name
        if isinstance(room1, CavernousRoom) and not isinstance(
            room2, CavernousRoom
        ):
            biome_name = room2.biome_name
        biome = config.get_biome(biome_name)
        width = choice(
            [1, 2, 3],
            weights=[
                biome.corridor_width_1_ratio,
                biome.corridor_width_2_ratio,
                biome.corridor_width_3_ratio,
            ],
        )
        if room1.in_maze or room2.in_maze:
            width = 3
        signature = (room1ix, room2ix, width, is_horizontal_first)
        if signature in prev_attempts:
            continue
        prev_attempts.add(signature)
        if room1.biome_name == room2.biome_name and room1.in_maze:
            continue
        corridor = carve_corridor(
            df, room1, room2, width, is_horizontal_first, biome_name
        )
        if not corridor:
            continue
        df.add_corridor(corridor)
        if not is_fully_connected and len(
            dfs(df.room_neighbors, room1ix)
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
            biome_name = corridor.biome_name
            if ptile.roomix == room1.ix and ntile.roomix != room2.ix:
                biome_name = room1.biome_name
            if ptile.roomix != room1.ix and ntile.roomix == room2.ix:
                biome_name = room2.biome_name
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
                new_tile = DoorTile(corridor.ix, biome_name=biome_name)
                df.set_tile(new_tile, x=x, y=y)
                new_door_locations.add((x, y, x - px, y - py))
        for x, y, dx, dy in new_door_locations:
            biome_name = df.get_tile(x=x, y=y).biome_name
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
                    new_tile = DoorTile(corridor.ix, biome_name=biome_name)
                    df.set_tile(new_tile, x=tx, y=ty)
        for x, y in corridor.walk(max_width_iter=1):
            tile = df.tiles[x][y]
            if not isinstance(tile, DoorTile):
                continue
            biome = df.config.get_biome(tile.biome_name)
            lock_dc = None
            if random.random() * 100.0 < biome.door_lock_percent:
                lock_dc = random_dc(biome.target_character_level)
            door = Door(
                Door.pick_type(biome),
                corridor,
                x,
                y,
                lock_dc=lock_dc,
                biome_name=tile.biome_name,
            )
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
    ladder_room_ixs = set()
    rooms = [x for x in df.rooms if not x.is_trivial()]
    roomlen = len(rooms)
    random.shuffle(rooms)

    # bias ourselves towards smallest rooms
    rooms.sort(key=lambda x: x.total_space())
    while len(rooms) < 2 * roomlen - 3:
        rooms = rooms + rooms[: int((2 * roomlen - len(rooms)) / 2 + 1)]

    # map from biome_name to [(roomix, x, y)]
    biome_up_ladders = collections.defaultdict(list)
    biome_down_ladders = collections.defaultdict(list)

    def biome_up_satisfied(biome_name):
        biome = df.config.get_biome(biome_name)
        return len(biome_up_ladders[biome_name]) >= biome.num_up_ladders

    def biome_satisfied(biome_name):
        biome = df.config.get_biome(biome_name)
        return (
            len(biome_up_ladders[biome_name]) >= biome.num_up_ladders
            and len(biome_down_ladders[biome_name]) >= biome.num_down_ladders
        )

    def all_satisfied():
        for biome_name in biome_name_set.union({None}):
            if not biome_satisfied(biome_name):
                return False
        return True

    biome_name_set = set()
    for room in rooms:
        if room.biome_name is not None:
            biome_name_set.add(room.biome_name)
    max_attempts = 50
    for attempt_ix in range(max_attempts):
        if all_satisfied():
            break
        ladder_room_ixs = set()
        biome_up_ladders = collections.defaultdict(list)
        biome_down_ladders = collections.defaultdict(list)
        for _ in range(20):
            biome_name_options = []
            for biome_name in biome_name_set:
                if not biome_satisfied(biome_name):
                    biome_name_options.append(biome_name)
            biome_name = None
            biome_rooms = rooms
            if biome_name_options:
                biome_name = random.choice(biome_name_options)
                biome_rooms = [r for r in rooms if r.biome_name == biome_name]
            elif biome_satisfied(None):
                break
            room = random.choice(biome_rooms)
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
            x, y = tile_coords
            tup = (room.ix, x, y)
            is_up = not biome_up_satisfied(biome_name)
            if is_up:
                biome_up_ladders[biome_name].append(tup)
                if biome_name is not None:
                    biome_up_ladders[None].append(tup)
            else:
                biome_down_ladders[biome_name].append(tup)
                if biome_name is not None:
                    biome_down_ladders[None].append(tup)
            ladder_room_ixs.add(room.ix)
    tups_seen = set()
    for l in biome_up_ladders.values():
        for tup in l:
            if tup in tups_seen:
                continue
            tups_seen.add(tup)
            roomix, x, y = tup
            room = df.rooms[roomix]
            df.set_tile(
                LadderUpTile(roomix, biome_name=room.biome_name), x=x, y=y
            )
            room.has_up_ladder = True
    for l in biome_down_ladders.values():
        for tup in l:
            if tup in tups_seen:
                continue
            tups_seen.add(tup)
            roomix, x, y = tup
            room = df.rooms[roomix]
            df.set_tile(
                LadderDownTile(roomix, biome_name=room.biome_name), x=x, y=y
            )
            room.has_down_ladder = True


def place_special_features_in_dungeon(df):
    features = []
    for biome in df.config.biomes + [df.config]:
        if random.random() * 100 < biome.blacksmith_percent:
            features.append(
                lib.features.Blacksmith(biome_name=biome.biome_name)
            )
            break
    for biome in df.config.biomes + [df.config]:
        if random.random() * 100 < biome.kryxix_altar_percent:
            features.append(
                lib.features.Altar(
                    deity_name="Kryxix", biome_name=biome.biome_name
                )
            )
            break
    for biome in df.config.biomes + [df.config]:
        if random.random() * 100 < biome.ssarthaxx_altar_percent:
            features.append(
                lib.features.Altar(
                    deity_name="Ssarthaxx", biome_name=biome.biome_name
                )
            )
            break
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
    for feature in features:
        feature.post_process(df)


def place_treasure_in_dungeon(df):
    lib = get_treasure_library("dnd 5e treasure")
    mimic_info = get_monster_library("dnd 5e monsters").get_monster_infos(
        "Mimic"
    )[0]
    room_biome_names = collections.defaultdict(list)
    for room in df.rooms:
        room_biome_names[room.biome_name].append(room)
    for biome_name, rooms in room_biome_names.items():
        biome = df.config.get_biome(biome_name)
        place_treasure_in_biome(df, biome, rooms, lib, mimic_info)


def place_treasure_in_biome(df, biome, rooms, lib, mimic_info):
    num_treasures = 0
    target_num_treasures = eval_dice(biome.num_treasures)
    num_mimics = 0
    target_num_mimics = eval_dice(biome.num_mimics)
    num_bookshelves = 0
    target_num_bookshelves = eval_dice(biome.num_bookshelves)
    eligible_rooms = []
    eligible_room_weights = []
    bookshelf_rooms = []
    bookshelf_room_weights = []
    for room in rooms:
        if not room.allows_treasure(df):
            continue
        if not room.corridorixs:
            continue
        weight = 1
        if len(room.corridorixs) == 1:
            weight *= 5
        weight *= math.sqrt(room.total_space())
        eligible_rooms.append(room)
        eligible_room_weights.append(weight)
        if room.allows_bookshelf(df):
            bookshelf_rooms.append(room)
            bookshelf_room_weights.append(weight)
    for _ in range(target_num_treasures * 10):
        if not eligible_rooms or num_treasures >= target_num_treasures:
            break
        room = random.choices(eligible_rooms, eligible_room_weights)[0]
        coords = room.pick_tile(
            df, unoccupied=True, avoid_corridor=True, prefer_wall=True
        )
        if not coords:
            continue
        x, y = coords
        contents = lib.gen_horde(
            biome.target_character_level,
            biome.num_player_characters,
        )
        if not contents:
            contents = ["Nothing!"]
        new_tile = ChestTile(
            room.ix, biome_name=room.biome_name, contents="\n".join(contents)
        )
        df.set_tile(new_tile, x=x, y=y)
        num_treasures += 1
    for _ in range(target_num_mimics * 10):
        if not eligible_rooms or num_mimics >= target_num_mimics:
            break
        room = random.choices(eligible_rooms, eligible_room_weights)[0]
        coords = room.pick_tile(
            df, unoccupied=True, avoid_corridor=True, prefer_wall=True
        )
        if not coords:
            continue
        x, y = coords
        monster = Monster(mimic_info)
        monster.adjust_cr(biome.target_character_level)
        nt = MimicTile(room.ix, biome_name=room.biome_name, monster=monster)
        df.set_tile(nt, x=x, y=y)
        num_mimics += 1
    for _ in range(target_num_bookshelves * 10):
        if not bookshelf_rooms or num_bookshelves >= target_num_bookshelves:
            break
        room = random.choices(bookshelf_rooms, bookshelf_room_weights)[0]
        coords = room.pick_tile(
            df, unoccupied=True, avoid_corridor=True, prefer_wall=True
        )
        if not coords:
            continue
        x, y = coords
        contents = lib.gen_bookshelf_horde(
            biome.target_character_level,
            biome.num_player_characters,
        )
        if not contents:
            contents = ["Nothing!"]
        new_tile = BookshelfTile(
            room.ix, biome_name=room.biome_name, contents="\n".join(contents)
        )
        df.set_tile(new_tile, x=x, y=y)
        num_bookshelves += 1


def place_monsters_in_dungeon(df):
    room_biome_names = collections.defaultdict(list)
    for room in df.rooms:
        room_biome_names[room.biome_name].append(room)
    monster_counts = collections.defaultdict(int)
    for biome_name, rooms in room_biome_names.items():
        biome = df.config.get_biome(biome_name)
        place_monsters_in_biome(df, biome, rooms, monster_counts)


def place_monsters_in_biome(df, biome, rooms, monster_counts):
    max_cr = int(math.ceil(biome.target_character_level * 7.0 / 5.0))
    monster_infos = get_monster_library("dnd 5e monsters").get_monster_infos(
        filter=biome.monster_filter,
        max_challenge_rating=max_cr,
        has_tts=True,
    )
    if not monster_infos:
        return  # no monsters matched whatever filters
    lowest_monster_xp = min((m.xp for m in monster_infos if m.xp))
    num_monster_encounters = 0
    target_monster_encounters = round(
        len(rooms) * biome.room_encounter_percent / 100.0
    )
    roomixs = []
    for room in rooms:
        if room.allows_enemies(df):
            roomixs.append(room.ix)
    random.shuffle(roomixs)
    roomixs = roomixs[:target_monster_encounters]
    roomixs.sort(key=lambda ix: df.rooms[ix].total_space())
    encounters = []
    for roomix in roomixs:
        lo = biome.encounter_xp_low_percent
        hi = biome.encounter_xp_high_percent
        xp_percent_of_medium = lo + random.random() * abs(hi - lo)
        target_xp = max(
            round(
                lib.monster.med_target_xp(biome) * xp_percent_of_medium * 0.01
            ),
            lowest_monster_xp,
        )
        enc = lib.monster.build_encounter(
            monster_infos,
            target_xp,
            prev_monster_counts=monster_counts,
            max_space=df.rooms[roomix].total_space(),
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
    for room in df.rooms:
        if not room.allows_traps(df):
            continue
        biome = df.config.get_biome(room.biome_name)
        if random.random() * 100.0 >= biome.room_trap_percent:
            continue
        trap = lib.trap.RoomTrap.create(biome, room)
        df.add_trap(trap)
        room.trapixs.add(trap.ix)

    for corridor in df.corridors:
        if corridor.is_trivial(df):
            continue
        biome = df.config.get_biome(corridor.biome_name)
        if random.random() * 100 >= biome.corridor_trap_percent:
            continue
        num_nearby_encounters = 0
        for roomix in [corridor.room1ix, corridor.room2ix]:
            room = df.rooms[roomix]
            if room.encounter:
                num_nearby_encounters += 1
        trap = lib.trap.CorridorTrap.create(
            biome, corridor, num_nearby_encounters=num_nearby_encounters
        )
        df.add_trap(trap)
        corridor.trapixs.add(trap.ix)

    for door in df.doors:
        corridor = df.corridors[door.corridorix]
        if corridor.trapixs:
            continue
        biome = df.config.get_biome(door.biome_name)
        if random.random() * 100 >= biome.door_trap_percent:
            continue
        trap = lib.trap.DoorTrap.create(biome, door.ix, door.x, door.y)
        df.add_trap(trap)
        door.trapixs.add(trap.ix)

    # chests
    for tile in df.get_tiles():
        if not tile.is_chest():
            continue
        biome = df.config.get_biome(tile.biome_name)
        if random.random() * 100 >= biome.chest_trap_percent:
            continue
        trap = lib.trap.ChestTrap.create(biome, tile.x, tile.y)
        df.add_trap(trap)
        tile.trapixs.add(trap.ix)


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
                thing_lights.append(lib.lights.GlowingMushrooms(x, y))
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
                thing_lights.append(lib.lights.WallSconce(x, y))
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


def add_npcs_to_dungeon(df):
    num_npcs = eval_dice(df.config.num_misc_NPCs)
    npc_list = list(lib.npcs.npc_library().values())
    num_npcs = min(num_npcs, len(npc_list))
    df.npcs += samples(npc_list, num_npcs)
