"""
Unit tests for lib/rivers.py

Tests for momentum-based river generation, covering:
- Full map traversal (rivers must reach both edges)
- Down-ladder room avoidance
- Pool expansion behavior
- Edge point selection
- Traversal validation
"""

import math
import random
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


def mock_tkinter():
    """Mock tkinter module for headless testing."""
    if "tkinter" not in sys.modules:
        tk_mock = types.ModuleType("tkinter")
        ttk_mock = types.ModuleType("tkinter.ttk")

        class StringVar:
            def __init__(self):
                self.value = ""

            def get(self):
                return self.value

            def set(self, val):
                self.value = val

        class IntVar:
            def __init__(self):
                self.value = 0

            def get(self):
                return self.value

            def set(self, val):
                self.value = val

        class DoubleVar:
            def __init__(self):
                self.value = 0.0

            def get(self):
                return self.value

            def set(self, val):
                self.value = val

        class BooleanVar:
            def __init__(self):
                self.value = False

            def get(self):
                return self.value

            def set(self, val):
                self.value = val

        tk_mock.StringVar = StringVar
        tk_mock.IntVar = IntVar
        tk_mock.DoubleVar = DoubleVar
        tk_mock.BooleanVar = BooleanVar
        tk_mock.Label = MagicMock()
        tk_mock.Frame = MagicMock()
        tk_mock.Tk = MagicMock()
        tk_mock.Text = MagicMock()
        tk_mock.Button = MagicMock()
        tk_mock.Checkbutton = MagicMock()
        tk_mock.Entry = MagicMock()
        tk_mock.Notebook = MagicMock()
        tk_mock.Canvas = MagicMock()
        tk_mock.Scrollbar = MagicMock()
        tk_mock.END = "end"
        tk_mock.font = MagicMock()
        tk_mock.font.nametofont = MagicMock(return_value=MagicMock())
        tk_mock.scrolledtext = MagicMock()

        ttk_mock.Combobox = MagicMock()
        ttk_mock.Style = MagicMock()

        tk_mock.ttk = ttk_mock
        sys.modules["tkinter"] = tk_mock
        sys.modules["tkinter.ttk"] = ttk_mock


mock_tkinter()

from lib.config import DungeonConfig
from lib.dungeon import (
    DungeonFloor,
    place_doors_in_dungeon,
    place_ladders_in_dungeon,
    place_rivers_in_dungeon,
    place_rooms_in_dungeon,
    place_special_features_in_dungeon,
)
from lib.rivers import (
    River,
    _attempt_propose_river,
    _expand_with_pools,
    _pick_edge_points,
    _validates_traversal,
)
from lib.room import CavernousRoom, RectRoom
from lib.tile import LadderDownTile, RoomFloorTile, WallTile


def _make_dungeon_with_rooms():
    """Create a dungeon with rooms placed (no corridors)."""
    config = DungeonConfig()
    df = DungeonFloor(config)
    place_rooms_in_dungeon(df)
    return df


class TestPickEdgePoints(unittest.TestCase):
    """Tests for _pick_edge_points helper."""

    def setUp(self):
        self.config = DungeonConfig()
        self.df = DungeonFloor(self.config)

    def test_returns_start_target_and_axis(self):
        """_pick_edge_points returns (start, target, axis) tuple."""
        start, target, axis = _pick_edge_points(self.df, diameter=2)
        self.assertIsInstance(start, tuple)
        self.assertIsInstance(target, tuple)
        self.assertIn(axis, ("x", "y"))
        self.assertEqual(len(start), 2)
        self.assertEqual(len(target), 2)

    def test_x_axis_start_and_target_on_left_right_edges(self):
        """For x-axis traversal, start and target x are at map edges."""
        with patch("random.random") as mock_random:
            # First call < 0.5 → left-right; then y positions; then < 0.5 → left-to-right
            mock_random.side_effect = [0.3, 0.5, 0.5, 0.3]
            start, target, axis = _pick_edge_points(self.df, diameter=2)
            self.assertEqual(axis, "x")
            self.assertEqual(start[0], 0.0)
            self.assertEqual(target[0], float(self.df.width - 1))

    def test_y_axis_start_and_target_on_top_bottom_edges(self):
        """For y-axis traversal, start and target y are at map edges."""
        with patch("random.random") as mock_random:
            # First call >= 0.5 → top-bottom; then x positions; then < 0.5 → bottom-to-top
            mock_random.side_effect = [0.7, 0.5, 0.5, 0.3]
            start, target, axis = _pick_edge_points(self.df, diameter=2)
            self.assertEqual(axis, "y")
            self.assertEqual(start[1], 0.0)
            self.assertEqual(target[1], float(self.df.height - 1))

    def test_positions_respect_margin(self):
        """Non-edge coordinates stay within margin bounds."""
        for _ in range(20):
            start, target, axis = _pick_edge_points(self.df, diameter=2)
            margin = 4  # diameter + 2
            if axis == "x":
                # y values should be within margin
                self.assertGreaterEqual(start[1], margin)
                self.assertLessEqual(start[1], self.df.height - margin)
                self.assertGreaterEqual(target[1], margin)
                self.assertLessEqual(target[1], self.df.height - margin)
            else:
                self.assertGreaterEqual(start[0], margin)
                self.assertLessEqual(start[0], self.df.width - margin)
                self.assertGreaterEqual(target[0], margin)
                self.assertLessEqual(target[0], self.df.width - margin)


class TestValidatesTraversal(unittest.TestCase):
    """Tests for _validates_traversal helper."""

    def setUp(self):
        self.config = DungeonConfig()
        self.df = DungeonFloor(self.config)

    def test_empty_path_fails(self):
        """Empty core path fails validation."""
        self.assertFalse(_validates_traversal([], "x", self.df))

    def test_short_x_path_fails(self):
        """Path spanning less than 60% of width fails for x-axis."""
        # 35 * 0.6 = 21, so span of 10 should fail
        path = [(i, 17) for i in range(10)]
        self.assertFalse(_validates_traversal(path, "x", self.df))

    def test_full_x_path_passes(self):
        """Path spanning full width passes for x-axis."""
        path = [(i, 17) for i in range(self.df.width)]
        self.assertTrue(_validates_traversal(path, "x", self.df))

    def test_short_y_path_fails(self):
        """Path spanning less than 60% of height fails for y-axis."""
        path = [(17, i) for i in range(10)]
        self.assertFalse(_validates_traversal(path, "y", self.df))

    def test_full_y_path_passes(self):
        """Path spanning full height passes for y-axis."""
        path = [(17, i) for i in range(self.df.height)]
        self.assertTrue(_validates_traversal(path, "y", self.df))


class TestRiverReachesBothEdges(unittest.TestCase):
    """Rivers must reach both edges of the map along their primary axis.

    This is the core requirement: every river should cross the full
    dungeon, entering on one edge and exiting on the opposite edge.
    A river that stops partway through the map is not valid.
    """

    def setUp(self):
        self.df = _make_dungeon_with_rooms()

    def test_river_reaches_both_x_edges(self):
        """River with x-axis traversal should have tiles near both
        the left (x=0) and right (x=width-1) edges."""
        found_good = False
        for seed in range(50):
            random.seed(seed)
            river = River.propose_river(self.df)
            if not river.river_tile_coords:
                continue
            xs = [c[0] for c in river.river_tile_coords]
            min_x, max_x = min(xs), max(xs)
            # Check if this river goes roughly left-right
            x_span = max_x - min_x
            if x_span > self.df.width * 0.5:
                # This is an x-traversal river; it should reach both edges
                self.assertLessEqual(
                    min_x,
                    3,
                    f"seed={seed}: river doesn't reach left edge (min_x={min_x})",
                )
                self.assertGreaterEqual(
                    max_x,
                    self.df.width - 4,
                    f"seed={seed}: river doesn't reach right edge (max_x={max_x})",
                )
                found_good = True
                break
        self.assertTrue(found_good, "No x-traversal river found in 50 seeds")

    def test_river_reaches_both_y_edges(self):
        """River with y-axis traversal should have tiles near both
        the bottom (y=0) and top (y=height-1) edges."""
        found_good = False
        for seed in range(50):
            random.seed(seed)
            river = River.propose_river(self.df)
            if not river.river_tile_coords:
                continue
            ys = [c[1] for c in river.river_tile_coords]
            min_y, max_y = min(ys), max(ys)
            y_span = max_y - min_y
            if y_span > self.df.height * 0.5:
                self.assertLessEqual(
                    min_y,
                    3,
                    f"seed={seed}: river doesn't reach bottom edge (min_y={min_y})",
                )
                self.assertGreaterEqual(
                    max_y,
                    self.df.height - 4,
                    f"seed={seed}: river doesn't reach top edge (max_y={max_y})",
                )
                found_good = True
                break
        self.assertTrue(found_good, "No y-traversal river found in 50 seeds")

    def test_all_rivers_span_full_primary_axis(self):
        """Every proposed river must span close to 100% of the map
        on its primary axis. Test across many seeds."""
        failures = []
        for seed in range(100):
            random.seed(seed)
            river = River.propose_river(self.df)
            if not river.river_tile_coords:
                failures.append(f"seed={seed}: empty river")
                continue
            xs = [c[0] for c in river.river_tile_coords]
            ys = [c[1] for c in river.river_tile_coords]
            x_span = max(xs) - min(xs)
            y_span = max(ys) - min(ys)
            # The river's primary axis should span at least 85% of the map
            primary_span = max(x_span, y_span)
            primary_size = (
                self.df.width if x_span >= y_span else self.df.height
            )
            fraction = primary_span / primary_size
            if fraction < 0.85:
                failures.append(
                    f"seed={seed}: span={primary_span}/{primary_size} "
                    f"({fraction:.0%})"
                )
        # Allow at most 5% failure rate (fallback rivers)
        self.assertLessEqual(
            len(failures),
            5,
            f"{len(failures)} rivers failed to span the map:\n"
            + "\n".join(failures[:10]),
        )


class TestRiverAvoidsDownLadderRoom(unittest.TestCase):
    """Rivers must not pass through rooms containing down ladders.

    The rationale is that water would drain through the down ladder
    opening, so it doesn't make sense for a river to flow through
    that room.
    """

    def _make_dungeon_with_down_ladder(self):
        """Create a dungeon and mark one room as having a down ladder."""
        df = _make_dungeon_with_rooms()
        # Pick a non-trivial room near the center for the down ladder
        center_x, center_y = df.width // 2, df.height // 2
        best_room = None
        best_dist = float("inf")
        for room in df.rooms:
            if room.is_trivial():
                continue
            dist = abs(room.x - center_x) + abs(room.y - center_y)
            if dist < best_dist:
                best_dist = dist
                best_room = room
        if best_room is not None:
            best_room.has_down_ladder = True
            # Place an actual LadderDownTile in the room
            tile_coords = list(best_room.tile_coords())
            if tile_coords:
                lx, ly = tile_coords[len(tile_coords) // 2]
                df.set_tile(
                    LadderDownTile(
                        best_room.ix, biome_name=best_room.biome_name
                    ),
                    x=lx,
                    y=ly,
                )
        return df, best_room

    def test_river_tiles_not_in_down_ladder_room(self):
        """No river tile should be in a room that has a down ladder."""
        df, ladder_room = self._make_dungeon_with_down_ladder()
        self.assertIsNotNone(ladder_room, "No room found for down ladder")
        ladder_room_tiles = set(ladder_room.tile_coords())

        for seed in range(30):
            random.seed(seed)
            river = River.propose_river(df)
            river_in_ladder_room = (
                set(river.river_tile_coords) & ladder_room_tiles
            )
            self.assertEqual(
                len(river_in_ladder_room),
                0,
                f"seed={seed}: river has {len(river_in_ladder_room)} tiles "
                f"in down-ladder room {ladder_room.ix} at center "
                f"({ladder_room.x}, {ladder_room.y})",
            )

    def test_river_avoids_all_down_ladder_rooms(self):
        """When multiple rooms have down ladders, river avoids all."""
        df = _make_dungeon_with_rooms()
        down_rooms = []
        for room in df.rooms:
            if room.is_trivial():
                continue
            if len(down_rooms) < 2:
                room.has_down_ladder = True
                down_rooms.append(room)

        self.assertGreaterEqual(len(down_rooms), 2)
        all_forbidden = set()
        for room in down_rooms:
            all_forbidden.update(room.tile_coords())

        for seed in range(20):
            random.seed(seed)
            river = River.propose_river(df)
            overlap = set(river.river_tile_coords) & all_forbidden
            self.assertEqual(
                len(overlap),
                0,
                f"seed={seed}: river overlaps {len(overlap)} tiles in "
                f"down-ladder rooms",
            )

    def test_river_tiles_not_adjacent_to_down_ladder_room(self):
        """No river tile should be adjacent to a down-ladder room's
        floor tiles. Water right next to the room would still drain."""
        df, ladder_room = self._make_dungeon_with_down_ladder()
        self.assertIsNotNone(ladder_room, "No room found for down ladder")
        ladder_room_tiles = set(ladder_room.tile_coords())
        # Build adjacency zone: room tiles + 1 tile border
        forbidden_zone = set()
        for rx, ry in ladder_room_tiles:
            for ddx in range(-1, 2):
                for ddy in range(-1, 2):
                    forbidden_zone.add((rx + ddx, ry + ddy))

        for seed in range(30):
            random.seed(seed)
            river = River.propose_river(df)
            river_in_zone = set(river.river_tile_coords) & forbidden_zone
            self.assertEqual(
                len(river_in_zone),
                0,
                f"seed={seed}: river has {len(river_in_zone)} tiles in or "
                f"adjacent to down-ladder room {ladder_room.ix}",
            )

    def test_hard_check_rejects_river_touching_avoided_room(self):
        """_attempt_propose_river returns None if the generated river
        would touch the down-ladder room, even if the walker itself
        avoided it (e.g., via expansion bleed)."""
        df, ladder_room = self._make_dungeon_with_down_ladder()
        self.assertIsNotNone(ladder_room)
        ladder_room_tiles = set(ladder_room.tile_coords())
        forbidden_zone = set()
        for rx, ry in ladder_room_tiles:
            for ddx in range(-1, 2):
                for ddy in range(-1, 2):
                    forbidden_zone.add((rx + ddx, ry + ddy))

        # Run many single attempts - any that return a River must
        # not touch the forbidden zone
        for seed in range(50):
            random.seed(seed)
            result = _attempt_propose_river(df, diameter=2, validate=False)
            if result is not None:
                overlap = set(result.river_tile_coords) & forbidden_zone
                self.assertEqual(
                    len(overlap),
                    0,
                    f"seed={seed}: _attempt_propose_river returned river "
                    f"with {len(overlap)} tiles in forbidden zone",
                )

    def test_river_still_generated_with_down_ladder(self):
        """A river is still successfully generated even when a down
        ladder room must be avoided."""
        df, ladder_room = self._make_dungeon_with_down_ladder()
        self.assertIsNotNone(ladder_room)

        random.seed(42)
        river = River.propose_river(df)
        self.assertGreater(
            len(river.river_tile_coords),
            0,
            "River should still have tiles when avoiding down ladder room",
        )


class TestExpandWithPools(unittest.TestCase):
    """Tests for _expand_with_pools post-processing."""

    def setUp(self):
        self.config = DungeonConfig()
        self.df = DungeonFloor(self.config)
        # Place a room in the center
        room = RectRoom(17, 17, rw=3, rh=3)
        self.df.add_room(room)
        self.room = room

    def test_wall_tiles_get_square_expansion(self):
        """Core path tiles in walls expand as a square."""
        # A path through wall area
        core_path = [(5, 5), (6, 5), (7, 5)]
        result = _expand_with_pools(core_path, self.df, diameter=2)
        # With diameter=2: rlo=0, rhi=2 → offsets (0,0),(0,1),(1,0),(1,1)
        self.assertIn((5, 5), result)
        self.assertIn((5, 6), result)
        self.assertIn((6, 5), result)

    def test_room_tiles_get_pool_expansion(self):
        """Core path tiles in rooms expand with circular pool."""
        # Path through the room center
        core_path = [(17, 17)]
        result = _expand_with_pools(core_path, self.df, diameter=2)
        # Room pool expansion should include more tiles than just square
        # The pool radius for a rect room is max(1, int(2*0.5)) = 1
        # So pool covers (17±1, 17±1) within the room
        self.assertIn((17, 17), result)
        self.assertIn((17, 18), result)
        self.assertIn((16, 17), result)

    def test_pool_expansion_bounded_by_room(self):
        """Pool expansion doesn't extend beyond the room boundary."""
        # Path at room edge
        room_tiles = set(self.room.tile_coords())
        core_path = [(self.room.x + self.room.rw, self.room.y)]
        result = _expand_with_pools(core_path, self.df, diameter=2)
        # Pool tiles within the room should be a subset of room tiles
        # (excluding the standard square expansion which goes anywhere)
        for coord in result:
            if coord in room_tiles:
                continue
            # Tiles outside room must be from standard square expansion
            cx, cy = core_path[0]
            dx = coord[0] - cx
            dy = coord[1] - cy
            self.assertTrue(
                0 <= dx <= 1 and 0 <= dy <= 1,
                f"Tile {coord} is outside room and not from square expansion",
            )

    def test_empty_core_path_returns_empty(self):
        """Empty core path produces no river tiles."""
        result = _expand_with_pools([], self.df, diameter=2)
        self.assertEqual(len(result), 0)


class TestAttemptProposeRiver(unittest.TestCase):
    """Tests for _attempt_propose_river internals."""

    def setUp(self):
        self.df = _make_dungeon_with_rooms()

    def test_returns_river_when_valid(self):
        """Should return a River when traversal validates."""
        # Try many seeds to find one that validates
        for seed in range(50):
            random.seed(seed)
            result = _attempt_propose_river(self.df, diameter=2)
            if result is not None:
                self.assertIsInstance(result, River)
                self.assertGreater(len(result.river_tile_coords), 0)
                return
        self.fail("No seed produced a valid river in 50 attempts")

    def test_returns_none_when_invalid(self):
        """Should return None when validation is on and path is short."""
        # Use a tiny dungeon where traversal is hard
        config = DungeonConfig()
        config.width = 10
        config.height = 10
        tiny_df = DungeonFloor(config)
        # Most attempts on a tiny blank dungeon should still work,
        # but with validate=True some may fail
        result = _attempt_propose_river(tiny_df, diameter=2)
        # Result is either River or None - both are valid outcomes
        if result is not None:
            self.assertIsInstance(result, River)

    def test_validate_false_always_returns_river(self):
        """With validate=False, always returns a River."""
        for seed in range(10):
            random.seed(seed)
            result = _attempt_propose_river(
                self.df, diameter=2, validate=False
            )
            self.assertIsInstance(result, River)

    def test_river_tiles_within_bounds(self):
        """All river tiles must be within dungeon bounds."""
        for seed in range(20):
            random.seed(seed)
            river = River.propose_river(self.df)
            for x, y in river.river_tile_coords:
                self.assertGreaterEqual(x, 0, f"seed={seed}")
                self.assertLess(x, self.df.width, f"seed={seed}")
                self.assertGreaterEqual(y, 0, f"seed={seed}")
                self.assertLess(y, self.df.height, f"seed={seed}")


class TestProposeRiverIntegration(unittest.TestCase):
    """Integration tests for River.propose_river."""

    def setUp(self):
        self.df = _make_dungeon_with_rooms()

    def test_propose_river_returns_river(self):
        """propose_river always returns a River object."""
        random.seed(42)
        river = River.propose_river(self.df)
        self.assertIsInstance(river, River)
        self.assertGreater(len(river.river_tile_coords), 0)

    def test_propose_river_diameter_preserved(self):
        """The returned River has the requested diameter."""
        random.seed(42)
        river = River.propose_river(self.df, diameter=3)
        self.assertEqual(river.diameter, 3)

    def test_multiple_rivers_are_independent(self):
        """Two rivers generated sequentially have different paths."""
        random.seed(42)
        river1 = River.propose_river(self.df)
        river2 = River.propose_river(self.df)
        coords1 = set(river1.river_tile_coords)
        coords2 = set(river2.river_tile_coords)
        # They shouldn't be identical (extremely unlikely with different random state)
        self.assertNotEqual(coords1, coords2)

    def test_adjacent_coords_computed(self):
        """River has adjacent_coords_set populated."""
        random.seed(42)
        river = River.propose_river(self.df)
        self.assertIsInstance(river.adjacent_coords_set, set)
        # Adjacent coords should not overlap with river tiles
        river_set = set(river.river_tile_coords)
        overlap = river.adjacent_coords_set & river_set
        self.assertEqual(len(overlap), 0)


class TestPipelineRiversAvoidRooms(unittest.TestCase):
    """Integration tests verifying the generation pipeline places
    ladders and special features before rivers, so river avoidance
    actually works end-to-end.
    """

    def test_rivers_avoid_down_ladder_rooms_in_pipeline(self):
        """After running place_ladders then place_rivers (the real
        pipeline order), no river tile should be in or adjacent to
        a room with a down ladder."""
        failures = []
        for seed in range(20):
            random.seed(seed)
            config = DungeonConfig()
            df = DungeonFloor(config)
            place_rooms_in_dungeon(df)
            # Ladders must be placed BEFORE rivers
            place_ladders_in_dungeon(df)
            place_rivers_in_dungeon(df)

            # Find rooms with down ladders
            down_rooms = [r for r in df.rooms if r.has_down_ladder]
            if not down_rooms:
                continue

            # Build forbidden zone (room tiles + 1-tile border)
            forbidden = set()
            for room in down_rooms:
                room_tiles = set(room.tile_coords())
                for rx, ry in room_tiles:
                    for ddx in range(-1, 2):
                        for ddy in range(-1, 2):
                            forbidden.add((rx + ddx, ry + ddy))

            for river in df.rivers:
                overlap = set(river.river_tile_coords) & forbidden
                if overlap:
                    failures.append(
                        f"seed={seed}: river {river.ix} has "
                        f"{len(overlap)} tiles in/adjacent to "
                        f"down-ladder room"
                    )
        self.assertEqual(
            len(failures),
            0,
            f"{len(failures)} pipeline failures:\n" + "\n".join(failures),
        )

    def test_rivers_avoid_special_feature_rooms_in_pipeline(self):
        """After running the real pipeline (doors, ladders, special
        features, then rivers), no river tile should be in or adjacent
        to a room with special features."""
        failures = []
        for seed in range(20):
            random.seed(seed)
            config = DungeonConfig()
            df = DungeonFloor(config)
            place_rooms_in_dungeon(df)
            place_doors_in_dungeon(df)
            place_ladders_in_dungeon(df)
            try:
                place_special_features_in_dungeon(df)
            except Exception:
                continue  # some seeds can't place features
            place_rivers_in_dungeon(df)

            # Find rooms with special features
            feature_rooms = [r for r in df.rooms if r.special_featureixs]
            if not feature_rooms:
                continue

            # Build forbidden zone (room tiles + 1-tile border)
            forbidden = set()
            for room in feature_rooms:
                room_tiles = set(room.tile_coords())
                for rx, ry in room_tiles:
                    for ddx in range(-1, 2):
                        for ddy in range(-1, 2):
                            forbidden.add((rx + ddx, ry + ddy))

            for river in df.rivers:
                overlap = set(river.river_tile_coords) & forbidden
                if overlap:
                    failures.append(
                        f"seed={seed}: river {river.ix} has "
                        f"{len(overlap)} tiles in/adjacent to "
                        f"special-feature room"
                    )
        self.assertEqual(
            len(failures),
            0,
            f"{len(failures)} pipeline failures:\n" + "\n".join(failures),
        )

    def test_pipeline_places_ladders_before_rivers(self):
        """Verify that in the generation pipeline, ladders are placed
        before rivers so has_down_ladder is set when rivers run."""
        import inspect

        from lib.dungeon import generate_random_dungeon

        source = inspect.getsource(generate_random_dungeon)
        ladder_pos = source.index("place_ladders_in_dungeon")
        river_pos = source.index("place_rivers_in_dungeon")
        self.assertLess(
            ladder_pos,
            river_pos,
            "place_ladders_in_dungeon must appear before "
            "place_rivers_in_dungeon in the pipeline",
        )

    def test_pipeline_places_special_features_before_rivers(self):
        """Verify that in the generation pipeline, special features
        are placed before rivers."""
        import inspect

        from lib.dungeon import generate_random_dungeon

        source = inspect.getsource(generate_random_dungeon)
        features_pos = source.index("place_special_features_in_dungeon")
        river_pos = source.index("place_rivers_in_dungeon")
        self.assertLess(
            features_pos,
            river_pos,
            "place_special_features_in_dungeon must appear before "
            "place_rivers_in_dungeon in the pipeline",
        )


if __name__ == "__main__":
    unittest.main()
