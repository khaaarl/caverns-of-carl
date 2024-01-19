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
from lib.room import Room, RectRoom, CavernousRoom
import lib.features
import lib.trap
from lib.treasure import get_treasure_library
from lib.utils import bfs, choice, dfs, eval_dice, neighbor_coords, samples


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


def generate_random_dungeon(config=None, errors=None):
    config = config or lib.config.DungeonConfig()
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
            df.rooms[corridor.room1ix].corridorixs.add(corridor.ix)
            df.rooms[corridor.room2ix].corridorixs.add(corridor.ix)
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
            door = Door(Door.pick_type(df.config), corridor, x, y)
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
    if random.random() < df.config.kryxix_altar_percent / 99.9:
        features.append(lib.features.Altar(deity_name="Kryxix"))
    if random.random() < df.config.ssarthaxx_altar_percent / 99.9:
        features.append(lib.features.Altar(deity_name="Ssarthaxx"))
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
    num_treasures = 0
    target_num_treasures = eval_dice(df.config.num_treasures)
    num_mimics = 0
    target_num_mimics = eval_dice(df.config.num_mimics)
    num_bookshelves = 0
    target_num_bookshelves = eval_dice(df.config.num_bookshelves)
    eligible_rooms = []
    eligible_room_weights = []
    bookshelf_rooms = []
    bookshelf_room_weights = []
    for room in df.rooms:
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
            df.config.target_character_level,
            df.config.num_player_characters,
        )
        if not contents:
            contents = ["Nothing!"]
        df.set_tile(ChestTile(room.ix, contents="\n".join(contents)), x=x, y=y)
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
        monster.adjust_cr(df.config.target_character_level)
        df.set_tile(MimicTile(room.ix, monster=monster), x=x, y=y)
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
            df.config.target_character_level,
            df.config.num_player_characters,
        )
        if not contents:
            contents = ["Nothing!"]
        df.set_tile(
            BookshelfTile(room.ix, contents="\n".join(contents)), x=x, y=y
        )
        num_bookshelves += 1


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
    for roomix in roomixs:
        lo = config.encounter_xp_low_percent
        hi = config.encounter_xp_high_percent
        xp_percent_of_medium = lo + random.random() * abs(hi - lo)
        target_xp = max(
            round(
                lib.monster.med_target_xp(config) * xp_percent_of_medium * 0.01
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
        num_nearby_encounters = 0
        for roomix in [corridor.room1ix, corridor.room2ix]:
            room = df.rooms[roomix]
            if room.encounter:
                num_nearby_encounters += 1
        trap = lib.trap.CorridorTrap.create(
            config, corridor, num_nearby_encounters=num_nearby_encounters
        )
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
