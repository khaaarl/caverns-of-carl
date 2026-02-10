from __future__ import annotations

import math
import random
from collections.abc import Iterable
from typing import TYPE_CHECKING

import lib.tts as tts
from lib.tile import CorridorFloorTile, WaterTile

if TYPE_CHECKING:
    from lib.dungeon import DungeonFloor

# --- Momentum walk tuning constants ---

# Random angular noise per step (std dev in radians)
DRIFT_STD = 0.08
# How much the previous angular change carries forward (0 = none, 1 = full)
MOMENTUM_DECAY = 0.7
# Base strength of pull toward the target exit point
TARGET_PULL_BASE = 0.03
# Additional target pull that ramps up as the walker crosses the map,
# ensuring it doesn't stall before reaching the far edge.
TARGET_PULL_RAMP = 0.12
# Strength of pull toward a room's center when inside a room
ROOM_CENTER_PULL = 0.04
# Strength of repulsion away from avoided rooms (down-ladder rooms)
AVOID_ROOM_REPULSION = 0.3
# Maximum angular change per step (radians)
MAX_TURN_RATE = 0.25
# Base step size in tile units
STEP_SIZE = 0.15

# Speed multipliers by terrain
SPEED_WALL = 1.2
SPEED_CORRIDOR = 1.0
SPEED_RECT_ROOM = 0.7
SPEED_CAVERN_ROOM = 0.5

# Pool expansion radii (multiplied by river diameter)
POOL_RADIUS_CAVERN = 1.0
POOL_RADIUS_RECT = 0.5

# Anti-stall: max steps with no new tile before terminating
STALL_LIMIT = 120
# Anti-loop: max re-entries to the same tile (re-entry = arriving after
# having left). This detects looping without penalizing slow traversal
# through a single tile at small step sizes.
MAX_TILE_REENTRIES = 2

# Minimum fraction of the primary axis the river must span
MIN_TRAVERSAL_FRACTION = 0.9
# Number of internal retries for propose_river
MAX_INTERNAL_RETRIES = 20


class River:
    """A momentum-based river that carves water tiles across the dungeon."""

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
        """Generate a momentum-based river path across the dungeon.

        Retries internally up to MAX_INTERNAL_RETRIES times to ensure
        the river traverses enough of the map.
        """
        for _ in range(MAX_INTERNAL_RETRIES):
            result = _attempt_propose_river(df, diameter)
            if result is not None:
                return result
        # Fallback: return whatever we get without validation
        result = _attempt_propose_river(df, diameter, validate=False)
        assert result is not None  # validate=False always returns a River
        return result

    def tts_fog_bits(self, df: DungeonFloor) -> list[tts.TTSFogBit]:
        """returns a list of fog bits: all small ones probably."""
        fogs: list[tts.TTSFogBit] = []
        coords = set(self.river_tile_coords).union(self.adjacent_coords_set)
        for x, y in coords:
            tile = df.get_tile(x=x, y=y)
            if tile and (tile.is_water() or tile.blocks_line_of_sight()):
                fogs.append(tts.TTSFogBit(x, y, riverixs=[self.ix]))
        return fogs


def _pick_edge_points(
    df: DungeonFloor, diameter: int
) -> tuple[tuple[float, float], tuple[float, float], str]:
    """Pick random start and target points on opposite map edges.

    Returns (start, target, primary_axis) where primary_axis is
    'x' if the river crosses left-right or 'y' for top-bottom.
    """
    margin = diameter + 2
    if random.random() < 0.5:
        # Left-right traversal
        start_y = margin + random.random() * (df.height - 2 * margin)
        target_y = margin + random.random() * (df.height - 2 * margin)
        if random.random() < 0.5:
            start_x, target_x = 0.0, float(df.width - 1)
        else:
            start_x, target_x = float(df.width - 1), 0.0
        return (start_x, start_y), (target_x, target_y), "x"
    else:
        # Top-bottom traversal
        start_x = margin + random.random() * (df.width - 2 * margin)
        target_x = margin + random.random() * (df.width - 2 * margin)
        if random.random() < 0.5:
            start_y, target_y = 0.0, float(df.height - 1)
        else:
            start_y, target_y = float(df.height - 1), 0.0
        return (start_x, start_y), (target_x, target_y), "y"


def _get_avoid_room_ixs(df: DungeonFloor) -> set[int]:
    """Return room indices the river must avoid.

    Includes rooms with down ladders and rooms with special features.
    """
    avoid = set()
    for room in df.rooms:
        if room.has_down_ladder or room.special_featureixs:
            avoid.add(room.ix)
    return avoid


def _build_avoid_zone(
    df: DungeonFloor, avoid_room_ixs: set[int]
) -> set[tuple[int, int]]:
    """Build the full exclusion zone for avoided rooms.

    Includes every floor tile in each avoided room PLUS a 1-tile
    border around those tiles, so the river cannot even be adjacent.
    """
    room_tiles: set[tuple[int, int]] = set()
    for rix in avoid_room_ixs:
        room = df.rooms[rix]
        room_tiles.update(room.tile_coords())

    zone: set[tuple[int, int]] = set()
    for rx, ry in room_tiles:
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                zone.add((rx + dx, ry + dy))
    return zone


def _attempt_propose_river(
    df: DungeonFloor, diameter: int, validate: bool = True
) -> River | None:
    """Single attempt at generating a momentum-based river path.

    Returns a River if successful (or if validate=False), None if
    the path doesn't meet traversal requirements.
    """
    # Avoid circular import at module level
    from lib.room import CavernousRoom, RectRoom

    start, target, primary_axis = _pick_edge_points(df, diameter)

    # Pre-compute total distance for adaptive target pull
    total_dist = math.hypot(target[0] - start[0], target[1] - start[1])
    if total_dist < 1.0:
        total_dist = 1.0

    # Pre-compute rooms to avoid (down-ladder rooms) and their tiles.
    # The avoid zone includes a 1-tile border so the river can't even
    # be adjacent to the room.
    avoid_room_ixs = _get_avoid_room_ixs(df)
    avoid_room_tiles = _build_avoid_zone(df, avoid_room_ixs)
    avoid_room_centers: list[tuple[float, float]] = []
    for rix in avoid_room_ixs:
        room = df.rooms[rix]
        avoid_room_centers.append((float(room.x), float(room.y)))

    x, y = start
    heading = math.atan2(target[1] - start[1], target[0] - start[0])
    speed = 1.0
    prev_turn = 0.0

    core_path: list[tuple[int, int]] = []
    core_set: set[tuple[int, int]] = set()
    reentry_counts: dict[tuple[int, int], int] = {}
    stall_counter = 0
    prev_coord: tuple[int, int] | None = None

    for _ in range(20000):
        ix, iy = int(x), int(y)

        # --- Check termination: out of bounds with margin ---
        if (
            x < -(diameter + 1)
            or x > df.width + diameter
            or y < -(diameter + 1)
            or y > df.height + diameter
        ):
            break

        # --- Record tile if in bounds and not in avoided room ---
        if 0 <= ix < df.width and 0 <= iy < df.height:
            coord = (ix, iy)
            if coord not in avoid_room_tiles:
                if coord not in core_set:
                    core_path.append(coord)
                    core_set.add(coord)
                    stall_counter = 0
                else:
                    stall_counter += 1
                    # Count re-entries: arriving at a tile we left before
                    if prev_coord is not None and prev_coord != coord:
                        reentry_counts[coord] = (
                            reentry_counts.get(coord, 0) + 1
                        )
                        if reentry_counts[coord] > MAX_TILE_REENTRIES:
                            break
            else:
                # In an avoided room tile - don't record but don't stall
                pass
            prev_coord = coord
        else:
            stall_counter += 1

        if stall_counter >= STALL_LIMIT:
            break

        # --- Sample terrain ---
        tile = (
            df.get_tile(x=ix, y=iy)
            if (0 <= ix < df.width and 0 <= iy < df.height)
            else None
        )

        current_room = None
        if tile is not None and tile.roomix is not None:
            current_room = df.rooms[tile.roomix]

        # --- Compute angular forces ---
        # 1. Random drift
        drift = random.gauss(0, DRIFT_STD)

        # 2. Momentum carry from previous turn
        momentum = prev_turn * MOMENTUM_DECAY

        # 3. Adaptive target pull - gets stronger as walker progresses
        #    across the map, ensuring it reaches the far edge.
        dist_to_target = math.hypot(target[0] - x, target[1] - y)
        progress = 1.0 - min(dist_to_target / total_dist, 1.0)
        target_pull = TARGET_PULL_BASE + TARGET_PULL_RAMP * progress
        angle_to_target = math.atan2(target[1] - y, target[0] - x)
        angle_diff = angle_to_target - heading
        # Normalize to [-pi, pi]
        angle_diff = (angle_diff + math.pi) % (2 * math.pi) - math.pi
        target_force = angle_diff * target_pull

        # 4. Room center pull - when in a non-avoided room, pull
        #    toward center
        room_force = 0.0
        if current_room is not None and current_room.ix not in avoid_room_ixs:
            angle_to_center = math.atan2(
                current_room.y - y, current_room.x - x
            )
            center_diff = angle_to_center - heading
            center_diff = (center_diff + math.pi) % (2 * math.pi) - math.pi
            room_force = center_diff * ROOM_CENTER_PULL

        # 5. Repulsion from avoided rooms (down-ladder rooms)
        avoid_force = 0.0
        for acx, acy in avoid_room_centers:
            dist_to_avoid = math.hypot(acx - x, acy - y)
            if dist_to_avoid < 8.0:  # Only repel when nearby
                # Push away from avoided room center
                angle_away = math.atan2(y - acy, x - acx)
                away_diff = angle_away - heading
                away_diff = (away_diff + math.pi) % (2 * math.pi) - math.pi
                strength = AVOID_ROOM_REPULSION / max(dist_to_avoid, 1.0)
                avoid_force += away_diff * strength

        # --- Sum and clamp angular change ---
        total_turn = drift + momentum + target_force + room_force + avoid_force
        total_turn = max(-MAX_TURN_RATE, min(MAX_TURN_RATE, total_turn))
        prev_turn = total_turn

        heading += total_turn

        # --- Adjust speed by terrain ---
        if tile is None or tile.is_wall():
            speed = SPEED_WALL
        elif current_room is not None:
            if isinstance(current_room, CavernousRoom):
                speed = SPEED_CAVERN_ROOM
            elif isinstance(current_room, RectRoom):
                speed = SPEED_RECT_ROOM
            else:
                speed = SPEED_CORRIDOR
        elif isinstance(tile, CorridorFloorTile):
            speed = SPEED_CORRIDOR
        else:
            speed = SPEED_CORRIDOR

        # --- Advance position ---
        x += speed * STEP_SIZE * math.cos(heading)
        y += speed * STEP_SIZE * math.sin(heading)

    # --- Validate traversal ---
    if validate and not _validates_traversal(core_path, primary_axis, df):
        return None

    # --- Expand core path into river tiles ---
    river_tile_coords = _expand_with_pools(
        core_path, df, diameter, avoid_room_tiles
    )

    # --- Hard post-check: reject if any river tile is in the
    #     avoid zone (room tiles + 1-tile border) ---
    if avoid_room_tiles and river_tile_coords & avoid_room_tiles:
        return None

    return River(diameter=diameter, river_tile_coords=river_tile_coords)


def _validates_traversal(
    core_path: list[tuple[int, int]],
    primary_axis: str,
    df: DungeonFloor,
) -> bool:
    """Check that the river spans at least MIN_TRAVERSAL_FRACTION of
    the map along its primary axis."""
    if not core_path:
        return False

    if primary_axis == "x":
        values = [c[0] for c in core_path]
        span = max(values) - min(values)
        return span >= df.width * MIN_TRAVERSAL_FRACTION
    else:
        values = [c[1] for c in core_path]
        span = max(values) - min(values)
        return span >= df.height * MIN_TRAVERSAL_FRACTION


def _expand_with_pools(
    core_path: list[tuple[int, int]],
    df: DungeonFloor,
    diameter: int,
    avoid_room_tiles: set[tuple[int, int]] | None = None,
) -> set[tuple[int, int]]:
    """Expand the core path into final river tile coordinates.

    In rooms, expands with circular pools (larger in caverns).
    Outside rooms, uses standard square expansion.
    Tiles in avoid_room_tiles are always excluded.
    """
    from lib.room import CavernousRoom

    if avoid_room_tiles is None:
        avoid_room_tiles = set()

    river_tile_coords: set[tuple[int, int]] = set()
    rlo = -math.floor((diameter - 1) / 2)
    rhi = math.ceil((diameter - 1) / 2) + 1

    # Pre-compute room tile sets for rooms the river passes through
    rooms_touched: set[int] = set()
    for x, y in core_path:
        tile = df.get_tile(x=x, y=y)
        if tile and tile.roomix is not None:
            rooms_touched.add(tile.roomix)

    room_tile_sets: dict[int, set[tuple[int, int]]] = {}
    for rix in rooms_touched:
        room = df.rooms[rix]
        room_tile_sets[rix] = set(room.tile_coords())

    for cx, cy in core_path:
        tile = df.get_tile(x=cx, y=cy)
        roomix = tile.roomix if tile else None

        if roomix is not None:
            # In a room: circular pool expansion
            room = df.rooms[roomix]
            if isinstance(room, CavernousRoom):
                pool_r = max(1, int(diameter * POOL_RADIUS_CAVERN))
            else:
                pool_r = max(1, int(diameter * POOL_RADIUS_RECT))

            allowed_tiles = room_tile_sets.get(roomix, set())
            for dx in range(-pool_r, pool_r + 1):
                for dy in range(-pool_r, pool_r + 1):
                    # Circular falloff
                    if dx * dx + dy * dy > pool_r * pool_r:
                        continue
                    tx, ty = cx + dx, cy + dy
                    if (
                        0 <= tx < df.width
                        and 0 <= ty < df.height
                        and (tx, ty) in allowed_tiles
                        and (tx, ty) not in avoid_room_tiles
                    ):
                        river_tile_coords.add((tx, ty))
            # Also add the standard square expansion so the river
            # doesn't narrow at room boundaries
            for dx in range(rlo, rhi):
                for dy in range(rlo, rhi):
                    tx, ty = cx + dx, cy + dy
                    if (
                        0 <= tx < df.width
                        and 0 <= ty < df.height
                        and (tx, ty) not in avoid_room_tiles
                    ):
                        river_tile_coords.add((tx, ty))
        else:
            # Outside rooms: standard square expansion
            for dx in range(rlo, rhi):
                for dy in range(rlo, rhi):
                    tx, ty = cx + dx, cy + dy
                    if (
                        0 <= tx < df.width
                        and 0 <= ty < df.height
                        and (tx, ty) not in avoid_room_tiles
                    ):
                        river_tile_coords.add((tx, ty))

    return river_tile_coords
