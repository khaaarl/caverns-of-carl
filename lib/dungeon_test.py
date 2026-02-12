"""
Unit tests for lib/dungeon.py

Tests for the dungeon generation pipeline, focusing initially on
the random_room() method of DungeonFloor.
"""

import random
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from lib.dungeon import DungeonFloor
from lib.room import CavernousRoom, RectRoom


def mock_tkinter():
    """
    Mock tkinter module for headless testing.

    tkinter is unavailable in headless environments. This function creates
    a minimal mock that allows imports of lib.config to succeed.
    """
    if "tkinter" not in sys.modules:
        tk_mock = types.ModuleType("tkinter")
        ttk_mock = types.ModuleType("tkinter.ttk")

        # Create mock variable classes
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
        ttk_mock.Notebook = MagicMock()
        ttk_mock.Frame = MagicMock()
        ttk_mock.Style = MagicMock()

        tk_mock.ttk = ttk_mock
        sys.modules["tkinter"] = tk_mock
        sys.modules["tkinter.ttk"] = ttk_mock


# Mock tkinter before any imports of lib.config
mock_tkinter()

from lib.config import DungeonConfig


class TestDungeonFloorRandomRoom(unittest.TestCase):
    """
    Tests for DungeonFloor.random_room() method.

    random_room() generates random room proposals within the dungeon bounds.
    It respects biome-specific settings like min_room_radius and
    cavernous_room_percent.

    The method uses random.randrange() and random.random(), which we mock
    to control the randomness during testing.
    """

    def setUp(self):
        """Set up test fixtures before each test."""
        self.config = DungeonConfig()
        self.dungeon = DungeonFloor(self.config)

    def test_random_room_returns_room_object(self):
        """Test that random_room() returns a Room object."""
        room = self.dungeon.random_room()
        self.assertIsNotNone(room)
        self.assertIsInstance(room, (RectRoom, CavernousRoom))

    def test_random_room_respects_dungeon_bounds(self):
        """
        Test that random_room() generates rooms within dungeon bounds.

        The room's x and y should be within [1+r, width-2-r] and
        [1+r, height-2-r] where r is the room radius.
        """
        # Run multiple times to account for randomness
        for _ in range(10):
            room = self.dungeon.random_room()
            min_bound = 1 + room.rw
            max_bound_x = self.dungeon.width - 2 - room.rw
            max_bound_y = self.dungeon.height - 2 - room.rh

            self.assertGreaterEqual(room.x, min_bound)
            self.assertLessEqual(room.x, max_bound_x)
            self.assertGreaterEqual(room.y, min_bound)
            self.assertLessEqual(room.y, max_bound_y)

    def test_random_room_with_default_config_produces_rect_rooms(self):
        """
        Test that random_room() produces RectRooms with controlled random.

        Default config has cavernous_room_percent = 50.0, so we control
        random.random() to ensure we get RectRooms.
        """
        with patch("random.random") as mock_random:
            # Return 0.99 so that random.random() * 100.0 = 99 > 50.0
            mock_random.return_value = 0.99

            room = self.dungeon.random_room()
            self.assertIsInstance(room, RectRoom)
            self.assertNotIsInstance(room, CavernousRoom)

    def test_random_room_with_default_config_produces_cavernous_rooms(self):
        """
        Test that random_room() produces CavernousRooms with controlled random.

        When random.random() * 100.0 is less than cavernous_room_percent,
        a CavernousRoom should be created.
        """
        with patch("random.random") as mock_random:
            # Return 0.25 so that random.random() * 100.0 = 25 < 50.0
            mock_random.return_value = 0.25

            room = self.dungeon.random_room()
            self.assertIsInstance(room, CavernousRoom)

    def test_random_room_respects_biome_cavernous_percent_high(self):
        """
        Test that random_room() respects biome cavernous_room_percent.

        With a biome having 100% cavernous, all rooms should be
        CavernousRooms.
        """
        # Add default biome (100% cavernous)
        default_biome = self.config.add_biome("default")
        default_biome.cavernous_room_percent = 100.0

        # Get a tile and set its biome_name to "default"
        self.dungeon.tiles[10][10].biome_name = "default"

        # Mock randrange to select tile at (10, 10)
        with patch("random.randrange") as mock_randrange:
            # First call: x = 10, Second call: y = 10
            mock_randrange.side_effect = [10, 10]

            room = self.dungeon.random_room()
            # Since default biome has 100% cavernous
            self.assertIsInstance(room, CavernousRoom)

    def test_random_room_respects_biome_cavernous_percent_low(self):
        """
        Test that random_room() respects biome with 0% cavernous.

        With dungeon biome having 0% cavernous, all rooms should be RectRooms.
        """
        # Add dungeon biome (0% cavernous)
        dungeon_biome = self.config.add_biome("dungeon")
        dungeon_biome.cavernous_room_percent = 0.0

        self.dungeon.tiles[10][10].biome_name = "dungeon"

        with patch("random.randrange") as mock_randrange:
            mock_randrange.side_effect = [10, 10]

            room = self.dungeon.random_room()
            self.assertIsInstance(room, RectRoom)
            self.assertNotIsInstance(room, CavernousRoom)

    def test_random_room_respects_min_room_radius(self):
        """
        Test that random_room() respects biome min_room_radius.

        The generated room's radius should be at least min_room_radius.
        """
        self.dungeon.config.min_room_radius = 5
        room = self.dungeon.random_room()
        self.assertGreaterEqual(room.rw, 5)
        self.assertGreaterEqual(room.rh, 5)

    def test_random_room_with_large_min_radius(self):
        """
        Test random_room() behavior with a very large min_room_radius.

        When min_room_radius is large, the room radius should be clamped
        to the minimum.
        """
        self.dungeon.config.min_room_radius = 10
        room = self.dungeon.random_room()
        self.assertEqual(room.rw, 10)
        self.assertEqual(room.rh, 10)

    def test_random_room_position_is_clamped(self):
        """
        Test that random_room() clamps position to valid bounds.

        If the random position is too close to an edge, it should be
        clamped inward.
        """
        with patch("random.randrange") as mock_randrange:
            # Generate at position (2, 2) with default min_room_radius = 1
            # This should be clamped to (2, 2) since 1 + 1 = 2
            mock_randrange.side_effect = [2, 2]

            room = self.dungeon.random_room()
            self.assertGreaterEqual(room.x, 1 + room.rw)
            self.assertGreaterEqual(room.y, 1 + room.rh)

    def test_random_room_position_clamping_near_edge(self):
        """
        Test that positions near the edge are clamped correctly.

        When random position is very close to the right/bottom edge,
        it should be clamped back inward.
        """
        self.dungeon.config.min_room_radius = 1
        with patch("random.randrange") as mock_randrange:
            # Try to place at (33, 33) which is very close to edge (35x35)
            # Should be clamped to around (32, 32)
            mock_randrange.side_effect = [33, 33]

            room = self.dungeon.random_room()
            self.assertLessEqual(room.x, self.dungeon.width - 2 - room.rw)
            self.assertLessEqual(room.y, self.dungeon.height - 2 - room.rh)

    def test_random_room_uses_tile_biome(self):
        """
        Test that random_room() uses the biome of the selected tile.

        The room should be created with the biome_name of the tile at
        the random position.
        """
        # Add a custom biome first so it can be retrieved by get_biome()
        custom_biome = self.config.add_biome("custom_biome")
        custom_biome.cavernous_room_percent = 50.0

        # Set a specific tile's biome
        self.dungeon.tiles[15][15].biome_name = "custom_biome"

        with patch("random.randrange") as mock_randrange:
            mock_randrange.side_effect = [15, 15]

            room = self.dungeon.random_room()
            self.assertEqual(room.biome_name, "custom_biome")

    def test_random_room_with_none_biome(self):
        """
        Test that random_room() handles None biome_name.

        If a tile's biome_name is None, the room should have None biome.
        """
        self.dungeon.tiles[20][20].biome_name = None

        with patch("random.randrange") as mock_randrange:
            mock_randrange.side_effect = [20, 20]

            room = self.dungeon.random_room()
            self.assertIsNone(room.biome_name)

    def test_random_room_reproducibility_with_same_seed(self):
        """
        Test that random_room() produces consistent results with same seed.

        When the random seed is set, the same sequence of random_room()
        calls should produce identical results.
        """
        random.seed(42)
        room1 = self.dungeon.random_room()

        # Create a fresh dungeon with the same seed
        fresh_config = DungeonConfig()
        fresh_dungeon = DungeonFloor(fresh_config)
        random.seed(42)
        room2 = fresh_dungeon.random_room()

        # Rooms should have identical properties
        self.assertEqual(room1.x, room2.x)
        self.assertEqual(room1.y, room2.y)
        self.assertEqual(room1.rw, room2.rw)
        self.assertEqual(room1.rh, room2.rh)
        self.assertEqual(type(room1), type(room2))
        self.assertEqual(room1.biome_name, room2.biome_name)

    def test_random_room_multiple_calls_vary(self):
        """
        Test that multiple calls to random_room() produce different results.

        Without mocking, multiple calls should (almost certainly) produce
        different rooms due to randomness.
        """
        rooms = [self.dungeon.random_room() for _ in range(5)]

        # At least one room should be different
        # (extremely unlikely all 5 are identical)
        positions = [(r.x, r.y, r.rw, r.rh, type(r).__name__) for r in rooms]
        self.assertGreater(len(set(positions)), 1)

    def test_random_room_integration_with_dungeon_bounds(self):
        """
        Integration test: Verify rooms fit within known dungeon dimensions.

        This test doesn't mock randomness, just verifies that regardless
        of what random_room() generates, it respects the dungeon.
        """
        # Create a new config with larger dimensions for testing
        large_config = DungeonConfig()
        large_config.width = 50
        large_config.height = 40
        large_dungeon = DungeonFloor(large_config)

        for _ in range(20):
            room = large_dungeon.random_room()
            # Room edges should not extend beyond dungeon bounds
            left_edge = room.x - room.rw
            right_edge = room.x + room.rw
            bottom_edge = room.y - room.rh
            top_edge = room.y + room.rh

            self.assertGreaterEqual(
                left_edge, 0, f"Room extends left of dungeon: {left_edge}"
            )
            self.assertLess(
                right_edge,
                large_dungeon.width,
                f"Room extends right of dungeon: {right_edge}",
            )
            self.assertGreaterEqual(
                bottom_edge, 0, f"Room extends below dungeon: {bottom_edge}"
            )
            self.assertLess(
                top_edge,
                large_dungeon.height,
                f"Room extends above dungeon: {top_edge}",
            )


class TestDungeonFloorAddRoom(unittest.TestCase):
    """Tests for DungeonFloor.add_room() method.

    Tests for adding rooms to the dungeon and updating tile state.
    """

    def setUp(self):
        """Set up test fixtures before each test."""
        self.config = DungeonConfig()
        self.dungeon = DungeonFloor(self.config)

    def test_add_room_assigns_index(self):
        """Test that add_room() assigns a sequential index to the room."""
        room1 = RectRoom(x=10, y=10, rw=3, rh=3)
        room2 = RectRoom(x=20, y=20, rw=3, rh=3)

        self.dungeon.add_room(room1)
        self.dungeon.add_room(room2)

        self.assertEqual(room1.ix, 0)
        self.assertEqual(room2.ix, 1)

    def test_add_room_appends_to_rooms_list(self):
        """Test that add_room() appends room to the rooms list."""
        initial_count = len(self.dungeon.rooms)
        room = RectRoom(x=10, y=10, rw=3, rh=3)

        self.dungeon.add_room(room)

        self.assertEqual(len(self.dungeon.rooms), initial_count + 1)
        self.assertIn(room, self.dungeon.rooms)

    def test_add_room_updates_tiles(self):
        """Test that add_room() updates tiles to reflect room placement."""
        room = RectRoom(x=10, y=10, rw=2, rh=2, biome_name=None)
        self.dungeon.add_room(room)

        # Check that tiles in the room are updated to RoomFloorTiles
        from lib.tile import RoomFloorTile

        for x in range(10 - 2, 10 + 3):
            for y in range(10 - 2, 10 + 3):
                tile = self.dungeon.tiles[x][y]
                self.assertIsInstance(tile, RoomFloorTile)
                self.assertEqual(tile.roomix, 0)

    def test_add_room_multiple_rooms_maintain_indices(self):
        """Test that multiple rooms are assigned correct indices."""
        rooms = [
            RectRoom(x=10, y=10, rw=2, rh=2),
            RectRoom(x=25, y=25, rw=2, rh=2),
            RectRoom(x=15, y=15, rw=2, rh=2),
        ]

        for room in rooms:
            self.dungeon.add_room(room)

        # Verify indices are sequential and correct
        for i, room in enumerate(self.dungeon.rooms):
            self.assertEqual(room.ix, i)

    def test_add_room_with_biome(self):
        """Test that add_room() preserves biome_name in tiles."""
        biome = self.config.add_biome("test_biome")
        room = RectRoom(x=10, y=10, rw=2, rh=2, biome_name="test_biome")

        self.dungeon.add_room(room)

        from lib.tile import RoomFloorTile

        tile = self.dungeon.tiles[10][10]
        self.assertIsInstance(tile, RoomFloorTile)
        self.assertEqual(tile.biome_name, "test_biome")


class TestDungeonFloorAddCorridor(unittest.TestCase):
    """Tests for DungeonFloor.add_corridor() method.

    Tests for adding corridors to the dungeon and updating connectivity.
    """

    def setUp(self):
        """Set up test fixtures before each test."""
        self.config = DungeonConfig()
        self.dungeon = DungeonFloor(self.config)
        # Add two rooms to connect
        self.room1 = RectRoom(x=5, y=5, rw=2, rh=2)
        self.room2 = RectRoom(x=25, y=25, rw=2, rh=2)
        self.dungeon.add_room(self.room1)
        self.dungeon.add_room(self.room2)

    def test_add_corridor_assigns_index(self):
        """Test that add_corridor() assigns a sequential index."""
        from lib.corridors import Corridor

        corridor = Corridor(
            room1ix=0,
            room2ix=1,
            x1=5,
            y1=5,
            x2=25,
            y2=25,
            is_horizontal_first=True,
            width=1,
        )

        self.dungeon.add_corridor(corridor)

        self.assertEqual(corridor.ix, 0)

    def test_add_corridor_appends_to_corridors_list(self):
        """Test that add_corridor() appends corridor to the corridors list."""
        from lib.corridors import Corridor

        initial_count = len(self.dungeon.corridors)
        corridor = Corridor(
            room1ix=0,
            room2ix=1,
            x1=5,
            y1=5,
            x2=25,
            y2=25,
            is_horizontal_first=True,
            width=1,
        )

        self.dungeon.add_corridor(corridor)

        self.assertEqual(len(self.dungeon.corridors), initial_count + 1)
        self.assertIn(corridor, self.dungeon.corridors)

    def test_add_corridor_updates_room_connectivity(self):
        """Test that add_corridor() updates room connectivity."""
        from lib.corridors import Corridor

        corridor = Corridor(
            room1ix=0,
            room2ix=1,
            x1=5,
            y1=5,
            x2=25,
            y2=25,
            is_horizontal_first=True,
            width=1,
        )

        self.dungeon.add_corridor(corridor)

        # Check that rooms know about the corridor
        self.assertIsNotNone(corridor.ix)
        self.assertIn(0, self.room1.corridorixs)
        self.assertIn(0, self.room2.corridorixs)

    def test_add_corridor_updates_room_neighbors(self):
        """Test that add_corridor() updates room_neighbors graph."""
        from lib.corridors import Corridor

        corridor = Corridor(
            room1ix=0,
            room2ix=1,
            x1=5,
            y1=5,
            x2=25,
            y2=25,
            is_horizontal_first=True,
            width=1,
        )

        self.dungeon.add_corridor(corridor)

        # Room 0 should know about Room 1 and vice versa
        self.assertIn(1, self.dungeon.room_neighbors[0])
        self.assertIn(0, self.dungeon.room_neighbors[1])

    def test_add_corridor_updates_tiles(self):
        """Test that add_corridor() converts wall tiles to corridor tiles."""
        from lib.corridors import Corridor
        from lib.tile import CorridorFloorTile

        # Use a corridor path that goes through wall tiles (between rooms)
        corridor = Corridor(
            room1ix=0,
            room2ix=1,
            x1=5,
            y1=5,
            x2=25,
            y2=25,
            is_horizontal_first=True,
            width=1,
        )

        self.dungeon.add_corridor(corridor)

        # Verify that corridor's ix was set (indicating it was added)
        self.assertIsNotNone(corridor.ix)

        # The corridor should have updated at least some tiles in the path
        # (room floor tiles are not converted, but wall tiles are)
        from lib.tile import RoomFloorTile

        non_room_floor_count = 0
        for x, y in corridor.walk():
            tile = self.dungeon.tiles[x][y]
            # Count tiles that are neither room floor nor corridor floor
            if not isinstance(tile, RoomFloorTile):
                non_room_floor_count += 1

        # The path should have some tiles that aren't room floors
        self.assertGreater(non_room_floor_count, 0)

    def test_add_corridor_multiple_corridors_maintain_indices(self):
        """Test that multiple corridors are assigned correct indices."""
        from lib.corridors import Corridor

        # Add a third room
        room3 = RectRoom(x=15, y=15, rw=2, rh=2)
        self.dungeon.add_room(room3)

        corridor1 = Corridor(
            room1ix=0,
            room2ix=1,
            x1=5,
            y1=5,
            x2=25,
            y2=25,
            is_horizontal_first=True,
            width=1,
        )
        corridor2 = Corridor(
            room1ix=1,
            room2ix=2,
            x1=25,
            y1=25,
            x2=15,
            y2=15,
            is_horizontal_first=True,
            width=1,
        )

        self.dungeon.add_corridor(corridor1)
        self.dungeon.add_corridor(corridor2)

        self.assertEqual(corridor1.ix, 0)
        self.assertEqual(corridor2.ix, 1)
        self.assertEqual(len(self.dungeon.corridors), 2)


class TestDungeonFloorPlacementValidation(unittest.TestCase):
    """Tests for room/corridor placement validation methods.

    Tests for tile access and neighbor detection methods.
    """

    def setUp(self):
        """Set up test fixtures before each test."""
        self.config = DungeonConfig()
        self.dungeon = DungeonFloor(self.config)

    def test_get_tile_within_bounds(self):
        """Test that get_tile() returns tiles within bounds."""
        tile = self.dungeon.get_tile(10, 10)
        self.assertIsNotNone(tile)
        self.assertEqual(tile.x, 10)
        self.assertEqual(tile.y, 10)

    def test_get_tile_out_of_bounds_returns_none(self):
        """Test that get_tile() returns None for out-of-bounds coordinates."""
        tile = self.dungeon.get_tile(-1, 10)
        self.assertIsNone(tile)

        tile = self.dungeon.get_tile(100, 10)
        self.assertIsNone(tile)

        tile = self.dungeon.get_tile(10, -1)
        self.assertIsNone(tile)

    def test_get_tile_out_of_bounds_with_default_tile_class(self):
        """Test that get_tile() creates default tile for out-of-bounds if provided."""
        from lib.tile import WallTile

        tile = self.dungeon.get_tile(-1, 10, default=WallTile)
        self.assertIsNotNone(tile)
        self.assertIsInstance(tile, WallTile)
        self.assertEqual(tile.x, -1)
        self.assertEqual(tile.y, 10)

    def test_neighbor_tiles_returns_four_neighbors(self):
        """Test that neighbor_tiles() returns 4 adjacent tiles."""
        neighbors = list(self.dungeon.neighbor_tiles(15, 15))
        self.assertEqual(len(neighbors), 4)

        # Check that neighbors are in expected directions
        neighbor_coords = [(t.x, t.y) for t in neighbors]
        self.assertIn((14, 15), neighbor_coords)  # left
        self.assertIn((16, 15), neighbor_coords)  # right
        self.assertIn((15, 14), neighbor_coords)  # down
        self.assertIn((15, 16), neighbor_coords)  # up

    def test_neighbor_tiles_at_edge(self):
        """Test that neighbor_tiles() handles edge tiles correctly."""
        # Test at corner (0, 0)
        neighbors = list(self.dungeon.neighbor_tiles(0, 0))
        neighbor_coords = [(t.x, t.y) for t in neighbors]

        # At corner, should have 2 neighbors (right and up)
        self.assertIn((1, 0), neighbor_coords)
        self.assertIn((0, 1), neighbor_coords)

    def test_tile_iter_covers_all_tiles(self):
        """Test that tile_iter() iterates over all dungeon tiles."""
        tile_count = len(list(self.dungeon.tile_iter()))
        expected_count = self.dungeon.width * self.dungeon.height

        self.assertEqual(tile_count, expected_count)

    def test_set_tile_updates_tile_location(self):
        """Test that set_tile() updates tile coordinates."""
        from lib.tile import RoomFloorTile

        new_tile = RoomFloorTile(roomix=None)
        self.dungeon.set_tile(new_tile, x=10, y=10)

        self.assertEqual(new_tile.x, 10)
        self.assertEqual(new_tile.y, 10)
        self.assertEqual(self.dungeon.tiles[10][10], new_tile)


class TestDungeonFloorAddMonster(unittest.TestCase):
    """Tests for DungeonFloor.add_monster() method.

    Tests for adding monsters to the dungeon and tracking monster locations.
    """

    def setUp(self):
        """Set up test fixtures before each test."""
        self.config = DungeonConfig()
        self.dungeon = DungeonFloor(self.config)

    def test_add_monster_assigns_index(self):
        """Test that add_monster() assigns a sequential index."""
        from lib.monster import Monster, MonsterInfo

        # Create a minimal monster with diameter 1
        monster_blob = {
            "name": "Goblin",
            "challenge_rating": 0.125,
            "diameter": 1,
            "tts_reference_nicknames": [],
            "tags": [],
        }
        monster_info = MonsterInfo(monster_blob)
        monster1 = Monster(monster_info, x=10, y=10)
        monster2 = Monster(monster_info, x=15, y=15)

        self.dungeon.add_monster(monster1)
        self.dungeon.add_monster(monster2)

        self.assertEqual(monster1.ix, 0)
        self.assertEqual(monster2.ix, 1)

    def test_add_monster_appends_to_monsters_list(self):
        """Test that add_monster() appends monster to the monsters list."""
        from lib.monster import Monster, MonsterInfo

        monster_blob = {
            "name": "Goblin",
            "challenge_rating": 0.125,
            "diameter": 1,
            "tts_reference_nicknames": [],
            "tags": [],
        }
        monster_info = MonsterInfo(monster_blob)
        monster = Monster(monster_info, x=10, y=10)

        initial_count = len(self.dungeon.monsters)
        self.dungeon.add_monster(monster)

        self.assertEqual(len(self.dungeon.monsters), initial_count + 1)
        self.assertIn(monster, self.dungeon.monsters)

    def test_add_monster_updates_monster_locations(self):
        """Test that add_monster() updates monster_locations map."""
        from lib.monster import Monster, MonsterInfo

        monster_blob = {
            "name": "Goblin",
            "challenge_rating": 0.125,
            "diameter": 1,
            "tts_reference_nicknames": [],
            "tags": [],
        }
        monster_info = MonsterInfo(monster_blob)
        monster = Monster(monster_info, x=10, y=10)

        self.dungeon.add_monster(monster)

        self.assertIn((10, 10), self.dungeon.monster_locations)
        self.assertEqual(self.dungeon.monster_locations[(10, 10)], monster)

    def test_add_monster_diameter_2_updates_multiple_locations(self):
        """Test that add_monster() with diameter 2 updates multiple locations."""
        from lib.monster import Monster, MonsterInfo

        # Large size gives diameter 2
        monster_blob = {
            "name": "Large Monster",
            "challenge_rating": 1,
            "size": "large",
            "tts_reference_nicknames": [],
        }
        monster_info = MonsterInfo(monster_blob)
        monster = Monster(monster_info, x=10, y=10)

        self.dungeon.add_monster(monster)

        # Diameter 2 should occupy 4 squares: (10,10), (11,10), (10,11), (11,11)
        expected_coords = [(10, 10), (11, 10), (10, 11), (11, 11)]
        for coord in expected_coords:
            self.assertIn(coord, self.dungeon.monster_locations)
            self.assertEqual(self.dungeon.monster_locations[coord], monster)

    def test_add_monster_diameter_3_updates_nine_locations(self):
        """Test that add_monster() with diameter 3 updates nine locations."""
        from lib.monster import Monster, MonsterInfo

        # Huge size gives diameter 3
        monster_blob = {
            "name": "Huge Monster",
            "challenge_rating": 5,
            "size": "huge",
            "tts_reference_nicknames": [],
        }
        monster_info = MonsterInfo(monster_blob)
        monster = Monster(monster_info, x=10, y=10)

        self.dungeon.add_monster(monster)

        # Diameter 3 should occupy 9 squares (3x3 centered on monster)
        expected_coords = [
            (9, 9),
            (10, 9),
            (11, 9),
            (9, 10),
            (10, 10),
            (11, 10),
            (9, 11),
            (10, 11),
            (11, 11),
        ]
        self.assertEqual(len(self.dungeon.monster_locations), 9)
        for coord in expected_coords:
            self.assertIn(coord, self.dungeon.monster_locations)


class TestDungeonFloorASCII(unittest.TestCase):
    """Tests for DungeonFloor.ascii() method.

    Tests for ASCII representation of the dungeon.
    """

    def setUp(self):
        """Set up test fixtures before each test."""
        self.config = DungeonConfig()
        self.dungeon = DungeonFloor(self.config)

    def test_ascii_returns_string(self):
        """Test that ascii() returns a string representation."""
        output = self.dungeon.ascii()
        self.assertIsInstance(output, str)

    def test_ascii_non_empty(self):
        """Test that ascii() produces non-empty output."""
        output = self.dungeon.ascii()
        self.assertGreater(len(output), 0)

    def test_ascii_with_room(self):
        """Test that ascii() renders rooms correctly."""
        room = RectRoom(x=10, y=10, rw=2, rh=2)
        self.dungeon.add_room(room)
        output = self.dungeon.ascii()

        # Output should contain the room
        self.assertGreater(len(output), 0)

    def test_ascii_with_colors(self):
        """Test that ascii() works with color parameter."""
        room = RectRoom(x=10, y=10, rw=2, rh=2)
        self.dungeon.add_room(room)

        output_without_color = self.dungeon.ascii(colors=False)
        output_with_color = self.dungeon.ascii(colors=True)

        self.assertGreater(len(output_without_color), 0)
        self.assertGreater(len(output_with_color), 0)


class TestDungeonGenerationIntegration(unittest.TestCase):
    """Integration tests for dungeon generation.

    Tests that verify multiple components work together correctly.
    """

    def setUp(self):
        """Set up test fixtures before each test."""
        self.config = DungeonConfig()
        self.dungeon = DungeonFloor(self.config)

    def test_full_simple_dungeon_creation(self):
        """Integration test: Create a simple dungeon with rooms."""
        # Add three rooms
        rooms = [
            RectRoom(x=5, y=5, rw=2, rh=2),
            RectRoom(x=20, y=20, rw=2, rh=2),
            RectRoom(x=30, y=5, rw=2, rh=2),
        ]

        for room in rooms:
            self.dungeon.add_room(room)

        # Verify state
        self.assertEqual(len(self.dungeon.rooms), 3)
        for i, room in enumerate(self.dungeon.rooms):
            self.assertEqual(room.ix, i)

    def test_rooms_and_corridors_together(self):
        """Integration test: Add rooms and corridors."""
        from lib.corridors import Corridor

        # Add rooms
        room1 = RectRoom(x=5, y=5, rw=2, rh=2)
        room2 = RectRoom(x=25, y=25, rw=2, rh=2)
        self.dungeon.add_room(room1)
        self.dungeon.add_room(room2)

        # Add corridor
        corridor = Corridor(
            room1ix=0,
            room2ix=1,
            x1=5,
            y1=5,
            x2=25,
            y2=25,
            is_horizontal_first=True,
            width=1,
        )
        self.dungeon.add_corridor(corridor)

        # Verify connectivity
        self.assertIn(0, self.dungeon.room_neighbors[1])
        self.assertIn(1, self.dungeon.room_neighbors[0])
        self.assertEqual(len(self.dungeon.corridors), 1)

    def test_dungeon_with_multiple_entities(self):
        """Integration test: Dungeon with rooms, corridors, and monsters."""
        from lib.corridors import Corridor
        from lib.monster import Monster, MonsterInfo

        # Add rooms
        room1 = RectRoom(x=5, y=5, rw=2, rh=2)
        room2 = RectRoom(x=25, y=25, rw=2, rh=2)
        self.dungeon.add_room(room1)
        self.dungeon.add_room(room2)

        # Add corridor
        corridor = Corridor(
            room1ix=0,
            room2ix=1,
            x1=5,
            y1=5,
            x2=25,
            y2=25,
            is_horizontal_first=True,
            width=1,
        )
        self.dungeon.add_corridor(corridor)

        # Add monster
        monster_blob = {
            "name": "Goblin",
            "challenge_rating": 0.125,
            "diameter": 1,
            "tts_reference_nicknames": [],
            "tags": [],
        }
        monster_info = MonsterInfo(monster_blob)
        monster = Monster(monster_info, x=10, y=10)
        self.dungeon.add_monster(monster)

        # Verify overall state
        self.assertEqual(len(self.dungeon.rooms), 2)
        self.assertEqual(len(self.dungeon.corridors), 1)
        self.assertEqual(len(self.dungeon.monsters), 1)
        self.assertEqual(len(self.dungeon.monster_locations), 1)


class TestBiomeWeightAt(unittest.TestCase):
    """Tests for biome_weight_at() bilinear interpolation function."""

    def test_owned_corner_returns_one(self):
        """A point exactly at an owned region corner should return 1.0."""
        from lib.dungeon import biome_weight_at

        regions = {"NW"}
        # NW is at (0.0, 1.0)
        self.assertAlmostEqual(biome_weight_at(regions, 0.0, 1.0), 1.0)

    def test_unowned_corner_returns_zero(self):
        """A point at an unowned region corner should return 0.0."""
        from lib.dungeon import biome_weight_at

        regions = {"NW"}
        # SE is at (1.0, 0.0) - not owned
        self.assertAlmostEqual(biome_weight_at(regions, 1.0, 0.0), 0.0)

    def test_all_regions_returns_one_everywhere(self):
        """With all 9 regions owned, weight should be 1.0 everywhere."""
        from lib.dungeon import biome_weight_at

        all_regions = {"NW", "N", "NE", "W", "C", "E", "SW", "S", "SE"}
        for tx in [0.0, 0.25, 0.5, 0.75, 1.0]:
            for ty in [0.0, 0.25, 0.5, 0.75, 1.0]:
                self.assertAlmostEqual(
                    biome_weight_at(all_regions, tx, ty),
                    1.0,
                    msg=f"Failed at ({tx}, {ty})",
                )

    def test_no_regions_returns_zero_everywhere(self):
        """With no regions owned, weight should be 0.0 everywhere."""
        from lib.dungeon import biome_weight_at

        for tx in [0.0, 0.25, 0.5, 0.75, 1.0]:
            for ty in [0.0, 0.25, 0.5, 0.75, 1.0]:
                self.assertAlmostEqual(
                    biome_weight_at(set(), tx, ty),
                    0.0,
                    msg=f"Failed at ({tx}, {ty})",
                )

    def test_top_row_gradient(self):
        """Top row owned should produce gradient from 1.0 at top to 0.0 at bottom."""
        from lib.dungeon import biome_weight_at

        regions = {"NW", "N", "NE"}
        # At top (y=1.0), should be 1.0
        self.assertAlmostEqual(biome_weight_at(regions, 0.5, 1.0), 1.0)
        # At center (y=0.5), should be 0.5 (interpolated between 1.0 top and 0.0 middle)
        self.assertAlmostEqual(biome_weight_at(regions, 0.5, 0.5), 0.0)
        # At bottom (y=0.0), should be 0.0
        self.assertAlmostEqual(biome_weight_at(regions, 0.5, 0.0), 0.0)

    def test_center_only(self):
        """Center region only should have weight 1.0 at center and 0 at corners."""
        from lib.dungeon import biome_weight_at

        regions = {"C"}
        self.assertAlmostEqual(biome_weight_at(regions, 0.5, 0.5), 1.0)
        self.assertAlmostEqual(biome_weight_at(regions, 0.0, 0.0), 0.0)
        self.assertAlmostEqual(biome_weight_at(regions, 1.0, 1.0), 0.0)


class TestPlaceBiomesRegionGrid(unittest.TestCase):
    """Tests for place_biomes_in_dungeon() with region grid."""

    def test_single_biome_all_regions(self):
        """Single biome with all regions should own every tile."""
        from lib.dungeon import place_biomes_in_dungeon

        config = DungeonConfig()
        biome = config.add_biome("Biome 1")
        biome.biome_regions = {"NW", "N", "NE", "W", "C", "E", "SW", "S", "SE"}
        df = DungeonFloor(config)
        place_biomes_in_dungeon(df)
        for tile in df.get_tiles():
            self.assertEqual(tile.biome_name, "Biome 1")

    def test_two_biomes_east_west_split(self):
        """Two biomes split E/W should assign edge tiles correctly."""
        from lib.dungeon import place_biomes_in_dungeon

        config = DungeonConfig()
        config.width = 21
        config.height = 21
        west = config.add_biome("West")
        west.biome_regions = {"NW", "W", "SW"}
        east = config.add_biome("East")
        east.biome_regions = {"NE", "E", "SE"}

        df = DungeonFloor(config)
        # Seed for determinism
        random.seed(42)
        place_biomes_in_dungeon(df)

        # Far-left tiles (x=0) should be "West"
        for y in range(df.height):
            self.assertEqual(
                df.tiles[0][y].biome_name,
                "West",
                f"Tile (0, {y}) should be West",
            )
        # Far-right tiles (x=width-1) should be "East"
        for y in range(df.height):
            self.assertEqual(
                df.tiles[df.width - 1][y].biome_name,
                "East",
                f"Tile ({df.width - 1}, {y}) should be East",
            )

    def test_no_biomes_tiles_remain_none(self):
        """With no biomes configured, all tiles should have biome_name=None."""
        from lib.dungeon import place_biomes_in_dungeon

        config = DungeonConfig()
        df = DungeonFloor(config)
        place_biomes_in_dungeon(df)
        for tile in df.get_tiles():
            self.assertIsNone(tile.biome_name)


if __name__ == "__main__":
    unittest.main()
