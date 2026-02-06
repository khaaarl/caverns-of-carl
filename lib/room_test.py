import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# Mock tkinter before importing config
tkinter_mock = types.ModuleType("tkinter")
tkinter_mock.StringVar = lambda: MagicMock(
    get=lambda: "test", set=lambda x: None
)
tkinter_mock.IntVar = lambda: MagicMock(get=lambda: 1, set=lambda x: None)
tkinter_mock.DoubleVar = lambda: MagicMock(get=lambda: 1.0, set=lambda x: None)
tkinter_mock.BooleanVar = lambda: MagicMock(
    get=lambda: False, set=lambda x: None
)
tkinter_mock.Frame = MagicMock
tkinter_mock.Label = MagicMock
tkinter_mock.Button = MagicMock
tkinter_mock.Canvas = MagicMock
tkinter_mock.Text = MagicMock
tkinter_mock.Entry = MagicMock
tkinter_mock.Listbox = MagicMock
tkinter_mock.ttk = types.ModuleType("ttk")
tkinter_mock.ttk.Combobox = MagicMock
tkinter_mock.font = types.ModuleType("font")
tkinter_mock.font.Font = MagicMock
sys.modules["tkinter"] = tkinter_mock
sys.modules["tkinter.ttk"] = tkinter_mock.ttk

from lib.room import CavernousRoom, MazeJunction, RectRoom, Room
from lib.tile import CorridorFloorTile, RoomFloorTile, WallTile


class TestRoomBase(unittest.TestCase):
    """Test the base Room class and common functionality."""

    def setUp(self):
        """Create test fixtures."""
        self.room = Room(x=10, y=10, rw=5, rh=5)

    def test_init_default_values(self):
        """Test Room initialization with default values."""
        room = Room(x=5, y=7)
        self.assertEqual(room.x, 5)
        self.assertEqual(room.y, 7)
        self.assertEqual(room.rw, 1)
        self.assertEqual(room.rh, 1)
        self.assertEqual(room.light_level, "bright")
        self.assertFalse(room.has_up_ladder)
        self.assertFalse(room.has_down_ladder)
        self.assertIsNone(room.ix)
        self.assertIsNone(room.encounter)
        self.assertEqual(room.special_featureixs, [])
        self.assertEqual(room.corridorixs, set())
        self.assertEqual(room.doorixs, set())
        self.assertEqual(room.trapixs, set())

    def test_init_with_custom_values(self):
        """Test Room initialization with custom values."""
        room = Room(x=20, y=30, rw=10, rh=15, biome_name="cave")
        self.assertEqual(room.x, 20)
        self.assertEqual(room.y, 30)
        self.assertEqual(room.rw, 10)
        self.assertEqual(room.rh, 15)
        self.assertEqual(room.biome_name, "cave")

    def test_init_enforces_minimum_dimensions(self):
        """Test that rw and rh are at least 1."""
        room = Room(x=5, y=5, rw=0, rh=-5)
        self.assertEqual(room.rw, 1)
        self.assertEqual(room.rh, 1)

    def test_has_ladder_up_only(self):
        """Test has_ladder returns True when only up_ladder is set."""
        self.room.has_up_ladder = True
        self.assertTrue(self.room.has_ladder())

    def test_has_ladder_down_only(self):
        """Test has_ladder returns True when only down_ladder is set."""
        self.room.has_down_ladder = True
        self.assertTrue(self.room.has_ladder())

    def test_has_ladder_both(self):
        """Test has_ladder returns True when both ladders are set."""
        self.room.has_up_ladder = True
        self.room.has_down_ladder = True
        self.assertTrue(self.room.has_ladder())

    def test_has_ladder_neither(self):
        """Test has_ladder returns False when neither ladder is set."""
        self.assertFalse(self.room.has_ladder())

    def test_tile_style_returns_dungeon(self):
        """Test that tile_style returns 'dungeon' by default."""
        self.assertEqual(self.room.tile_style(), "dungeon")

    def test_new_floor_tile_creates_room_floor(self):
        """Test that new_floor_tile creates a RoomFloorTile."""
        self.room.ix = 0
        tile = self.room.new_floor_tile()
        self.assertIsInstance(tile, RoomFloorTile)
        self.assertEqual(tile.roomix, 0)
        self.assertEqual(tile.tile_style, "dungeon")

    def test_new_floor_tile_with_biome(self):
        """Test that new_floor_tile includes biome name."""
        self.room.ix = 1
        self.room.biome_name = "forest"
        tile = self.room.new_floor_tile()
        self.assertEqual(tile.biome_name, "forest")

    def test_tile_coords_not_implemented(self):
        """Test that tile_coords raises NotImplementedError on base Room."""
        with self.assertRaises(NotImplementedError):
            list(self.room.tile_coords())

    def test_is_trivial_default_false(self):
        """Test that is_trivial returns False by default."""
        self.assertFalse(self.room.is_trivial())

    def test_total_space_not_implemented(self):
        """Test that total_space works via tile_coords."""
        # Base Room doesn't implement tile_coords, so this should raise
        with self.assertRaises(NotImplementedError):
            self.room.total_space()

    def test_is_fully_enclosed_by_doors_no_doors(self):
        """Test is_fully_enclosed_by_doors when no doors."""
        self.assertFalse(self.room.is_fully_enclosed_by_doors())

    def test_is_fully_enclosed_by_doors_fewer_doors_than_corridors(self):
        """Test is_fully_enclosed_by_doors when doors < corridors."""
        self.room.doorixs = {0}
        self.room.corridorixs = {0, 1, 2}
        self.assertFalse(self.room.is_fully_enclosed_by_doors())

    def test_is_fully_enclosed_by_doors_same_count(self):
        """Test is_fully_enclosed_by_doors when doors == corridors."""
        self.room.doorixs = {0, 1}
        self.room.corridorixs = {0, 1}
        self.assertTrue(self.room.is_fully_enclosed_by_doors())

    def test_desires_doors_not_implemented(self):
        """Test that desires_doors returns NotImplementedError on base Room."""
        # Note: The base Room.desires_doors() returns NotImplementedError (not raises)
        result = self.room.desires_doors()
        # The source code returns the exception, not raises it
        self.assertIsInstance(result, NotImplementedError)

    def test_embiggened_increases_size(self):
        """Test that embiggened creates a room with increased dimensions."""
        room = Room(x=5, y=5, rw=2, rh=2)
        with patch("random.randrange") as mock_rand:
            mock_rand.side_effect = [1, 1]  # Both increase by 1
            bigger = room.embiggened()
            self.assertEqual(bigger.x, 5)
            self.assertEqual(bigger.y, 5)
            self.assertEqual(bigger.rw, 3)
            self.assertEqual(bigger.rh, 3)

    def test_embiggened_preserves_position_and_biome(self):
        """Test that embiggened preserves position and biome."""
        room = Room(x=10, y=20, rw=3, rh=3, biome_name="swamp")
        with patch("random.randrange", return_value=0):
            bigger = room.embiggened()
            self.assertEqual(bigger.x, 10)
            self.assertEqual(bigger.y, 20)
            self.assertEqual(bigger.biome_name, "swamp")

    def test_wiggled_offset_position(self):
        """Test that wiggled creates room with offset position."""
        room = Room(x=10, y=10, rw=2, rh=2)
        with patch("random.randrange") as mock_rand:
            mock_rand.side_effect = [0, 1]  # x offset 0, y offset 1
            wiggled = room.wiggled()
            self.assertEqual(wiggled.x, 10)
            self.assertEqual(wiggled.y, 11)
            self.assertEqual(wiggled.rw, 2)
            self.assertEqual(wiggled.rh, 2)

    def test_wiggled_negative_offset(self):
        """Test that wiggled can apply negative offsets."""
        room = Room(x=10, y=10, rw=2, rh=2)
        with patch("random.randrange", return_value=-1):
            wiggled = room.wiggled()
            self.assertEqual(wiggled.x, 9)
            self.assertEqual(wiggled.y, 9)


class TestRectRoom(unittest.TestCase):
    """Test RectRoom (rectangular rooms)."""

    def setUp(self):
        """Create test fixtures."""
        self.room = RectRoom(x=10, y=10, rw=2, rh=3)

    def test_init_is_rect_room(self):
        """Test that RectRoom initializes correctly."""
        self.assertEqual(self.room.x, 10)
        self.assertEqual(self.room.y, 10)
        self.assertEqual(self.room.rw, 2)
        self.assertEqual(self.room.rh, 3)

    def test_tile_coords_single_cell(self):
        """Test tile_coords for minimum size room (enforced to 1x1)."""
        # Note: Room constructor enforces minimum rw=1, rh=1
        room = RectRoom(x=5, y=5, rw=0, rh=0)
        self.assertEqual(room.rw, 1)  # Enforced to minimum
        self.assertEqual(room.rh, 1)  # Enforced to minimum
        coords = set(room.tile_coords())
        # Should be 3x3 (from 4,4 to 6,6)
        self.assertEqual(len(coords), 9)

    def test_tile_coords_3x3_room(self):
        """Test tile_coords for 3x3 room (rw=1, rh=1)."""
        room = RectRoom(x=5, y=5, rw=1, rh=1)
        coords = set(room.tile_coords())
        expected = {
            (4, 4),
            (4, 5),
            (4, 6),
            (5, 4),
            (5, 5),
            (5, 6),
            (6, 4),
            (6, 5),
            (6, 6),
        }
        self.assertEqual(coords, expected)

    def test_tile_coords_5x7_room(self):
        """Test tile_coords for 5x7 room (rw=2, rh=3)."""
        room = RectRoom(x=10, y=10, rw=2, rh=3)
        coords = set(room.tile_coords())
        # Width: 10-2 to 10+2 = 5 cells, Height: 10-3 to 10+3 = 7 cells
        self.assertEqual(len(coords), 5 * 7)
        # Check corners
        self.assertIn((8, 7), coords)
        self.assertIn((12, 13), coords)

    def test_total_space_formula(self):
        """Test total_space calculation."""
        room = RectRoom(x=5, y=5, rw=3, rh=4)
        # (1 + 3*2) * (1 + 4*2) = 7 * 9 = 63
        self.assertEqual(room.total_space(), 63)

    def test_total_space_matches_tile_coords(self):
        """Test that total_space matches actual tile_coords count."""
        room = RectRoom(x=10, y=10, rw=2, rh=3)
        self.assertEqual(room.total_space(), len(list(room.tile_coords())))

    def test_desires_doors_true(self):
        """Test that RectRoom desires_doors returns True."""
        self.assertTrue(self.room.desires_doors())

    def test_tile_style_returns_dungeon(self):
        """Test that RectRoom tile_style is dungeon."""
        self.assertEqual(self.room.tile_style(), "dungeon")


class TestMazeJunction(unittest.TestCase):
    """Test MazeJunction (trivial maze intersection rooms)."""

    def setUp(self):
        """Create test fixtures."""
        self.room = MazeJunction(x=15, y=15, rw=1, rh=1)

    def test_init_is_maze_junction(self):
        """Test that MazeJunction initializes as RectRoom."""
        self.assertEqual(self.room.x, 15)
        self.assertEqual(self.room.y, 15)
        self.assertEqual(self.room.rw, 1)
        self.assertEqual(self.room.rh, 1)

    def test_is_trivial_true(self):
        """Test that MazeJunction is_trivial returns True."""
        self.assertTrue(self.room.is_trivial())

    def test_desires_doors_false(self):
        """Test that MazeJunction desires_doors returns False."""
        self.assertFalse(self.room.desires_doors())

    def test_tile_coords_inherited_from_rect(self):
        """Test that tile_coords works like RectRoom."""
        coords = set(self.room.tile_coords())
        expected = {
            (14, 14),
            (14, 15),
            (14, 16),
            (15, 14),
            (15, 15),
            (15, 16),
            (16, 14),
            (16, 15),
            (16, 16),
        }
        self.assertEqual(coords, expected)

    def test_allows_treasure_false(self):
        """Test that MazeJunction allows_treasure returns False."""
        df = MagicMock()
        self.assertFalse(self.room.allows_treasure(df))

    def test_allows_bookshelf_false(self):
        """Test that MazeJunction allows_bookshelf returns False."""
        df = MagicMock()
        self.assertFalse(self.room.allows_bookshelf(df))

    def test_allows_enemies_false(self):
        """Test that MazeJunction allows_enemies returns False."""
        df = MagicMock()
        self.assertFalse(self.room.allows_enemies(df))

    def test_allows_traps_false(self):
        """Test that MazeJunction allows_traps returns False."""
        df = MagicMock()
        self.assertFalse(self.room.allows_traps(df))

    def test_maze_coordinates_initialized(self):
        """Test that maze_x and maze_y are initialized."""
        self.assertIsNone(self.room.maze_x)
        self.assertIsNone(self.room.maze_y)

    def test_maze_coordinates_can_be_set(self):
        """Test that maze coordinates can be set."""
        self.room.maze_x = 5
        self.room.maze_y = 7
        self.assertEqual(self.room.maze_x, 5)
        self.assertEqual(self.room.maze_y, 7)


class TestCavernousRoom(unittest.TestCase):
    """Test CavernousRoom (irregular eroded rooms)."""

    def setUp(self):
        """Create test fixtures."""
        self.room = CavernousRoom(x=20, y=20, rw=5, rh=5)

    def test_init_is_cavernous_room(self):
        """Test that CavernousRoom initializes correctly."""
        self.assertEqual(self.room.x, 20)
        self.assertEqual(self.room.y, 20)
        self.assertEqual(self.room.rw, 5)
        self.assertEqual(self.room.rh, 5)
        self.assertIsNone(self.room.explicit_tile_coords)

    def test_tile_style_returns_cavern(self):
        """Test that CavernousRoom tile_style is 'cavern'."""
        self.assertEqual(self.room.tile_style(), "cavern")

    def test_tile_coords_lazy_initialization(self):
        """Test that tile_coords lazily initializes explicit_tile_coords."""
        self.assertIsNone(self.room.explicit_tile_coords)
        coords = list(self.room.tile_coords())
        self.assertIsNotNone(self.room.explicit_tile_coords)
        self.assertEqual(coords, self.room.explicit_tile_coords)

    def test_tile_coords_ellipse_boundary(self):
        """Test that tile_coords respects ellipse equation."""
        room = CavernousRoom(x=10, y=10, rw=3, rh=3)
        coords = set(room.tile_coords())
        # Center should be included
        self.assertIn((10, 10), coords)
        # Points just outside ellipse should not be included
        # Far corners are definitely outside
        self.assertNotIn((6, 6), coords)  # Corner at (-4, -4)
        self.assertNotIn((14, 14), coords)  # Corner at (4, 4)

    def test_tile_coords_caches_result(self):
        """Test that tile_coords returns cached result on second call."""
        coords1 = list(self.room.tile_coords())
        coords2 = list(self.room.tile_coords())
        self.assertEqual(coords1, coords2)
        # Both should reference same cached list
        self.assertIs(
            self.room.explicit_tile_coords, self.room.explicit_tile_coords
        )

    def test_total_space_ellipse_approximation(self):
        """Test that total_space approximates ellipse area."""
        # For a circle with rw=rh=r, area ~= pi*r^2
        room = CavernousRoom(x=10, y=10, rw=4, rh=4)
        space = room.total_space()
        # pi * 4^2 ~= 50.3, but the ellipse equation includes boundary cases
        # so space should be somewhat close to ellipse area
        self.assertGreater(space, 30)
        self.assertLess(space, 75)

    def test_desires_doors_false(self):
        """Test that CavernousRoom desires_doors returns False."""
        self.assertFalse(self.room.desires_doors())

    def test_allows_bookshelf_false(self):
        """Test that CavernousRoom allows_bookshelf returns False."""
        df = MagicMock()
        self.assertFalse(self.room.allows_bookshelf(df))

    def test_allows_treasure_true_by_default(self):
        """Test that CavernousRoom allows_treasure by default."""
        df = MagicMock()
        df.special_features = []
        self.room.special_featureixs = []
        self.assertTrue(self.room.allows_treasure(df))

    def test_tile_coords_small_room(self):
        """Test tile_coords for very small cavernous room."""
        room = CavernousRoom(x=5, y=5, rw=1, rh=1)
        coords = set(room.tile_coords())
        # Should at least contain center
        self.assertIn((5, 5), coords)

    def test_new_floor_tile_cavern_style(self):
        """Test that new_floor_tile has cavern style."""
        self.room.ix = 2
        tile = self.room.new_floor_tile()
        self.assertEqual(tile.tile_style, "cavern")


class TestRoomWithMocking(unittest.TestCase):
    """Test Room methods that interact with DungeonFloor (mocked)."""

    def setUp(self):
        """Create test fixtures."""
        self.room = RectRoom(x=10, y=10, rw=1, rh=1)
        self.room.ix = 0
        # Mock DungeonFloor
        self.df = MagicMock()
        self.df.special_features = []
        self.df.monster_locations = set()

    def test_allows_treasure_no_ladder(self):
        """Test allows_treasure returns True when no ladder."""
        self.assertFalse(self.room.has_ladder())
        self.assertTrue(self.room.allows_treasure(self.df))

    def test_allows_treasure_with_up_ladder(self):
        """Test allows_treasure returns False when up_ladder is set."""
        self.room.has_up_ladder = True
        self.assertFalse(self.room.allows_treasure(self.df))

    def test_allows_treasure_with_down_ladder(self):
        """Test allows_treasure returns False when down_ladder is set."""
        self.room.has_down_ladder = True
        self.assertFalse(self.room.allows_treasure(self.df))

    def test_allows_enemies_no_ladder(self):
        """Test allows_enemies returns True when no ladder."""
        self.assertFalse(self.room.has_ladder())
        self.assertTrue(self.room.allows_enemies(self.df))

    def test_allows_enemies_with_ladder(self):
        """Test allows_enemies returns False when ladder is set."""
        self.room.has_up_ladder = True
        self.assertFalse(self.room.allows_enemies(self.df))

    def test_allows_traps_no_ladder(self):
        """Test allows_traps returns True when no ladder."""
        self.assertFalse(self.room.has_ladder())
        self.assertTrue(self.room.allows_traps(self.df))

    def test_allows_traps_with_ladder(self):
        """Test allows_traps returns False when ladder is set."""
        self.room.has_down_ladder = True
        self.assertFalse(self.room.allows_traps(self.df))

    def test_allows_bookshelf_default_true(self):
        """Test allows_bookshelf returns True by default."""
        self.assertTrue(self.room.allows_bookshelf(self.df))

    def test_pick_tile_selects_from_room(self):
        """Test pick_tile returns a valid room coordinate."""

        # Set up tiles
        def mock_get_tile(x, y):
            return RoomFloorTile(0, biome_name=None)

        self.df.get_tile = mock_get_tile
        self.df.tiles = {
            x: {y: RoomFloorTile(0, biome_name=None) for y in range(5, 16)}
            for x in range(5, 16)
        }
        self.df.neighbor_tiles = MagicMock(return_value=[])

        result = self.room.pick_tile(self.df)
        self.assertIsNotNone(result)
        x, y = result
        # Result should be within room bounds
        self.assertGreaterEqual(x, 9)
        self.assertLessEqual(x, 11)
        self.assertGreaterEqual(y, 9)
        self.assertLessEqual(y, 11)

    def test_pick_tile_returns_none_if_impossible(self):
        """Test pick_tile returns None if no valid tile found."""

        # Block all tiles
        def mock_floor_tile(roomix, biome_name=None):
            t = RoomFloorTile(roomix, biome_name=biome_name)
            t.is_move_blocking = lambda: True
            return t

        self.df.tiles = {
            x: {y: mock_floor_tile(0) for y in range(5, 16)}
            for x in range(5, 16)
        }
        self.df.get_tile = lambda x, y: mock_floor_tile(0)
        self.df.monster_locations = set()

        result = self.room.pick_tile(self.df, unoccupied=True)
        # Should eventually give up and return None
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
