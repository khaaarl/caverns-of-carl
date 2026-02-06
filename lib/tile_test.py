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

from lib.tile import (
    BookshelfTile,
    ChestTile,
    CorridorFloorTile,
    DoorTile,
    FloorTile,
    LadderDownTile,
    LadderUpTile,
    MimicTile,
    RoomFloorTile,
    SecretDoorTile,
    Tile,
    WallTile,
    WaterTile,
    rotY_away_from_wall,
)


class TestBaseTile(unittest.TestCase):
    """Test the base Tile class."""

    def setUp(self):
        """Create test fixtures."""
        self.tile = Tile()

    def test_init_default(self):
        """Test Tile initialization with defaults."""
        self.assertIsNone(self.tile.x)
        self.assertIsNone(self.tile.y)
        self.assertIsNone(self.tile.tile_style)
        self.assertIsNone(self.tile.roomix)
        self.assertIsNone(self.tile.corridorix)
        self.assertIsNone(self.tile.doorix)
        self.assertEqual(self.tile.riverixs, set())
        self.assertEqual(self.tile.trapixs, set())
        self.assertEqual(self.tile.light_level, "bright")
        self.assertFalse(self.tile.is_interior)
        self.assertIsNone(self.tile.biome_name)

    def test_init_with_params(self):
        """Test Tile initialization with parameters."""
        tile = Tile(x=5, y=10, biome_name="forest")
        self.assertEqual(tile.x, 5)
        self.assertEqual(tile.y, 10)
        self.assertEqual(tile.biome_name, "forest")

    def test_to_char_default(self):
        """Test that base Tile to_char returns '?'."""
        self.assertEqual(self.tile.to_char(), "?")

    def test_is_move_blocking_default_true(self):
        """Test that base Tile is_move_blocking returns True."""
        self.assertTrue(self.tile.is_move_blocking())

    def test_is_feature_default_false(self):
        """Test that base Tile is_feature returns False."""
        self.assertFalse(self.tile.is_feature())

    def test_is_ladder_default_false(self):
        """Test that base Tile is_ladder returns False."""
        self.assertFalse(self.tile.is_ladder())

    def test_is_chest_default_false(self):
        """Test that base Tile is_chest returns False."""
        self.assertFalse(self.tile.is_chest())

    def test_is_water_default_false(self):
        """Test that base Tile is_water returns False."""
        self.assertFalse(self.tile.is_water())

    def test_is_wall_default_false(self):
        """Test that base Tile is_wall returns False."""
        self.assertFalse(self.tile.is_wall())

    def test_is_door_default_false(self):
        """Test that base Tile is_door returns False."""
        self.assertFalse(self.tile.is_door())

    def test_blocks_line_of_sight_default_false(self):
        """Test that base Tile blocks_line_of_sight returns False."""
        self.assertFalse(self.tile.blocks_line_of_sight())

    def test_light_level_assignment(self):
        """Test that light_level can be changed."""
        self.tile.light_level = "dim"
        self.assertEqual(self.tile.light_level, "dim")
        self.tile.light_level = "dark"
        self.assertEqual(self.tile.light_level, "dark")

    def test_riverixs_is_set(self):
        """Test that riverixs is a set and can be updated."""
        self.tile.riverixs.add(0)
        self.tile.riverixs.add(1)
        self.assertEqual(self.tile.riverixs, {0, 1})

    def test_trapixs_is_set(self):
        """Test that trapixs is a set and can be updated."""
        self.tile.trapixs.add(0)
        self.assertEqual(self.tile.trapixs, {0})


class TestWallTile(unittest.TestCase):
    """Test WallTile class."""

    def setUp(self):
        """Create test fixtures."""
        self.tile = WallTile()

    def test_is_wall_true(self):
        """Test that WallTile is_wall returns True."""
        self.assertTrue(self.tile.is_wall())

    def test_blocks_line_of_sight_true(self):
        """Test that WallTile blocks_line_of_sight returns True."""
        self.assertTrue(self.tile.blocks_line_of_sight())

    def test_to_char_dungeon_not_interior(self):
        """Test WallTile to_char for dungeon (not interior)."""
        self.tile.tile_style = "dungeon"
        self.tile.is_interior = False
        char = self.tile.to_char()
        self.assertIn("#", char)

    def test_to_char_cavern_not_interior(self):
        """Test WallTile to_char for cavern (not interior)."""
        self.tile.tile_style = "cavern"
        self.tile.is_interior = False
        char = self.tile.to_char()
        self.assertIn("#", char)

    def test_to_char_interior(self):
        """Test WallTile to_char for interior walls (appears as space)."""
        self.tile.is_interior = True
        char = self.tile.to_char()
        self.assertEqual(char, " ")

    def test_is_move_blocking_default(self):
        """Test WallTile is_move_blocking (inherited, should be True)."""
        self.assertTrue(self.tile.is_move_blocking())


class TestFloorTile(unittest.TestCase):
    """Test FloorTile class."""

    def setUp(self):
        """Create test fixtures."""
        self.tile = FloorTile()

    def test_is_move_blocking_false(self):
        """Test that FloorTile is_move_blocking returns False."""
        self.assertFalse(self.tile.is_move_blocking())

    def test_is_wall_false(self):
        """Test that FloorTile is_wall returns False."""
        self.assertFalse(self.tile.is_wall())

    def test_is_feature_default_false(self):
        """Test that FloorTile is_feature returns False."""
        self.assertFalse(self.tile.is_feature())


class TestRoomFloorTile(unittest.TestCase):
    """Test RoomFloorTile class."""

    def setUp(self):
        """Create test fixtures."""
        self.tile = RoomFloorTile(roomix=0)

    def test_init_sets_roomix(self):
        """Test that RoomFloorTile stores roomix."""
        self.assertEqual(self.tile.roomix, 0)

    def test_init_with_other_params(self):
        """Test RoomFloorTile with x, y, and biome_name."""
        tile = RoomFloorTile(roomix=5, x=10, y=20, biome_name="swamp")
        self.assertEqual(tile.roomix, 5)
        self.assertEqual(tile.x, 10)
        self.assertEqual(tile.y, 20)
        self.assertEqual(tile.biome_name, "swamp")

    def test_to_char_dungeon(self):
        """Test RoomFloorTile to_char for dungeon."""
        self.tile.tile_style = "dungeon"
        char = self.tile.to_char()
        self.assertIn(".", char)

    def test_to_char_cavern(self):
        """Test RoomFloorTile to_char for cavern."""
        self.tile.tile_style = "cavern"
        char = self.tile.to_char()
        self.assertIn(".", char)

    def test_is_move_blocking_false(self):
        """Test that RoomFloorTile is_move_blocking returns False."""
        self.assertFalse(self.tile.is_move_blocking())


class TestCorridorFloorTile(unittest.TestCase):
    """Test CorridorFloorTile class."""

    def setUp(self):
        """Create test fixtures."""
        self.tile = CorridorFloorTile(corridorix=0)

    def test_init_sets_corridorix(self):
        """Test that CorridorFloorTile stores corridorix."""
        self.assertEqual(self.tile.corridorix, 0)

    def test_init_with_other_params(self):
        """Test CorridorFloorTile with x, y, and biome_name."""
        tile = CorridorFloorTile(corridorix=3, x=5, y=15, biome_name="cave")
        self.assertEqual(tile.corridorix, 3)
        self.assertEqual(tile.x, 5)
        self.assertEqual(tile.y, 15)

    def test_to_char_dungeon(self):
        """Test CorridorFloorTile to_char for dungeon."""
        self.tile.tile_style = "dungeon"
        char = self.tile.to_char()
        self.assertIn(",", char)

    def test_to_char_cavern(self):
        """Test CorridorFloorTile to_char for cavern."""
        self.tile.tile_style = "cavern"
        char = self.tile.to_char()
        self.assertIn(",", char)

    def test_is_move_blocking_false(self):
        """Test that CorridorFloorTile is_move_blocking returns False."""
        self.assertFalse(self.tile.is_move_blocking())


class TestDoorTile(unittest.TestCase):
    """Test DoorTile class."""

    def setUp(self):
        """Create test fixtures."""
        self.tile = DoorTile(corridorix=0, doorix=0)

    def test_init_sets_corridorix_and_doorix(self):
        """Test that DoorTile stores both corridorix and doorix."""
        self.assertEqual(self.tile.corridorix, 0)
        self.assertEqual(self.tile.doorix, 0)

    def test_is_door_true(self):
        """Test that DoorTile is_door returns True."""
        self.assertTrue(self.tile.is_door())

    def test_is_move_blocking_true(self):
        """Test that DoorTile is_move_blocking returns True."""
        self.assertTrue(self.tile.is_move_blocking())

    def test_blocks_line_of_sight_true(self):
        """Test that DoorTile blocks_line_of_sight returns True."""
        self.assertTrue(self.tile.blocks_line_of_sight())

    def test_to_char_plus(self):
        """Test that DoorTile to_char returns '+'."""
        self.assertEqual(self.tile.to_char(), "+")

    def test_is_move_blocking_overrides_floor_tile(self):
        """Test that DoorTile overrides FloorTile's is_move_blocking."""
        # DoorTile extends CorridorFloorTile which extends FloorTile
        # but DoorTile should return True
        self.assertTrue(self.tile.is_move_blocking())


class TestSecretDoorTile(unittest.TestCase):
    """Test SecretDoorTile class."""

    def setUp(self):
        """Create test fixtures."""
        self.tile = SecretDoorTile(corridorix=1, doorix=5)

    def test_init_sets_corridorix_and_doorix(self):
        """Test that SecretDoorTile stores both corridorix and doorix."""
        self.assertEqual(self.tile.corridorix, 1)
        self.assertEqual(self.tile.doorix, 5)

    def test_is_door_true(self):
        """Test that SecretDoorTile is_door returns True."""
        self.assertTrue(self.tile.is_door())

    def test_to_char_dungeon(self):
        """Test SecretDoorTile to_char for dungeon."""
        self.tile.tile_style = "dungeon"
        char = self.tile.to_char()
        self.assertIn("S", char)

    def test_to_char_cavern(self):
        """Test SecretDoorTile to_char for cavern."""
        self.tile.tile_style = "cavern"
        char = self.tile.to_char()
        self.assertIn("S", char)


class TestLadderTiles(unittest.TestCase):
    """Test LadderUpTile and LadderDownTile classes."""

    def test_ladder_up_init(self):
        """Test LadderUpTile initialization."""
        tile = LadderUpTile(roomix=2)
        self.assertEqual(tile.roomix, 2)

    def test_ladder_up_is_ladder_true(self):
        """Test that LadderUpTile is_ladder returns True."""
        tile = LadderUpTile(roomix=0)
        self.assertTrue(tile.is_ladder())

    def test_ladder_up_is_move_blocking_true(self):
        """Test that LadderUpTile is_move_blocking returns True."""
        tile = LadderUpTile(roomix=0)
        self.assertTrue(tile.is_move_blocking())

    def test_ladder_up_to_char(self):
        """Test that LadderUpTile to_char returns '<'."""
        tile = LadderUpTile(roomix=0)
        self.assertIn("<", tile.to_char())

    def test_ladder_down_init(self):
        """Test LadderDownTile initialization."""
        tile = LadderDownTile(roomix=3)
        self.assertEqual(tile.roomix, 3)

    def test_ladder_down_is_ladder_true(self):
        """Test that LadderDownTile is_ladder returns True."""
        tile = LadderDownTile(roomix=0)
        self.assertTrue(tile.is_ladder())

    def test_ladder_down_is_move_blocking_true(self):
        """Test that LadderDownTile is_move_blocking returns True."""
        tile = LadderDownTile(roomix=0)
        self.assertTrue(tile.is_move_blocking())

    def test_ladder_down_to_char(self):
        """Test that LadderDownTile to_char returns '>'."""
        tile = LadderDownTile(roomix=0)
        self.assertIn(">", tile.to_char())


class TestChestTile(unittest.TestCase):
    """Test ChestTile class."""

    def setUp(self):
        """Create test fixtures."""
        self.tile = ChestTile(roomix=0, contents="Gold coins")

    def test_init_stores_contents(self):
        """Test that ChestTile stores contents."""
        self.assertEqual(self.tile.contents, "Gold coins")

    def test_init_with_empty_contents(self):
        """Test ChestTile with empty contents."""
        tile = ChestTile(roomix=1)
        self.assertEqual(tile.contents, "")

    def test_is_chest_true(self):
        """Test that ChestTile is_chest returns True."""
        self.assertTrue(self.tile.is_chest())

    def test_is_feature_true(self):
        """Test that ChestTile is_feature returns True."""
        self.assertTrue(self.tile.is_feature())

    def test_is_move_blocking_true(self):
        """Test that ChestTile is_move_blocking returns True."""
        self.assertTrue(self.tile.is_move_blocking())

    def test_to_char_dollar(self):
        """Test that ChestTile to_char returns '$'."""
        char = self.tile.to_char()
        self.assertIn("$", char)

    def test_is_room_floor_tile(self):
        """Test that ChestTile extends RoomFloorTile."""
        self.assertEqual(self.tile.roomix, 0)

    def test_contents_multiline(self):
        """Test that ChestTile can have multiline contents."""
        contents = "Gold coins\nSilver ring\nPotion"
        tile = ChestTile(roomix=0, contents=contents)
        self.assertEqual(tile.contents, contents)


class TestBookshelfTile(unittest.TestCase):
    """Test BookshelfTile class."""

    def setUp(self):
        """Create test fixtures."""
        self.tile = BookshelfTile(roomix=0, contents="Book: Spellcraft")

    def test_init_stores_contents(self):
        """Test that BookshelfTile stores contents."""
        self.assertEqual(self.tile.contents, "Book: Spellcraft")

    def test_is_feature_true(self):
        """Test that BookshelfTile is_feature returns True."""
        self.assertTrue(self.tile.is_feature())

    def test_is_move_blocking_false(self):
        """Test that BookshelfTile is_move_blocking returns False."""
        self.assertFalse(self.tile.is_move_blocking())

    def test_to_char_b(self):
        """Test that BookshelfTile to_char returns 'B'."""
        char = self.tile.to_char()
        self.assertIn("B", char)

    def test_is_chest_true(self):
        """Test that BookshelfTile is_chest returns True (inherited from ChestTile)."""
        self.assertTrue(self.tile.is_chest())


class TestMimicTile(unittest.TestCase):
    """Test MimicTile class."""

    def setUp(self):
        """Create test fixtures."""
        self.mock_monster = MagicMock()
        self.tile = MimicTile(roomix=0, monster=self.mock_monster)

    def test_init_stores_monster(self):
        """Test that MimicTile stores monster."""
        self.assertEqual(self.tile.monster, self.mock_monster)

    def test_init_with_explicit_contents(self):
        """Test MimicTile with explicit contents parameter."""
        monster = MagicMock()
        tile = MimicTile(roomix=0, monster=monster, contents="test")
        self.assertEqual(tile.contents, "test")

    def test_to_char_m(self):
        """Test that MimicTile to_char returns 'm'."""
        self.assertEqual(self.tile.to_char(), "m")

    def test_is_feature_true(self):
        """Test that MimicTile is_feature returns True."""
        self.assertTrue(self.tile.is_feature())

    def test_is_chest_true(self):
        """Test that MimicTile is_chest returns True (inherited from ChestTile)."""
        self.assertTrue(self.tile.is_chest())


class TestWaterTile(unittest.TestCase):
    """Test WaterTile class."""

    def setUp(self):
        """Create test fixtures."""
        self.tile = WaterTile()

    def test_is_water_true(self):
        """Test that WaterTile is_water returns True."""
        self.assertTrue(self.tile.is_water())

    def test_to_char_tilde(self):
        """Test that WaterTile to_char returns '~'."""
        char = self.tile.to_char()
        self.assertIn("~", char)

    def test_is_move_blocking_true(self):
        """Test that WaterTile is_move_blocking returns True (inherited from Tile)."""
        self.assertTrue(self.tile.is_move_blocking())

    def test_is_wall_false(self):
        """Test that WaterTile is_wall returns False."""
        self.assertFalse(self.tile.is_wall())


class TestTileHierarchy(unittest.TestCase):
    """Test the tile class hierarchy relationships."""

    def test_wall_tile_inheritance(self):
        """Test that WallTile inherits from Tile."""
        tile = WallTile()
        self.assertIsInstance(tile, Tile)

    def test_floor_tile_inheritance(self):
        """Test that FloorTile inherits from Tile."""
        tile = FloorTile()
        self.assertIsInstance(tile, Tile)

    def test_room_floor_tile_inheritance(self):
        """Test that RoomFloorTile inherits from FloorTile."""
        tile = RoomFloorTile(roomix=0)
        self.assertIsInstance(tile, FloorTile)
        self.assertIsInstance(tile, Tile)

    def test_corridor_floor_tile_inheritance(self):
        """Test that CorridorFloorTile inherits from FloorTile."""
        tile = CorridorFloorTile(corridorix=0)
        self.assertIsInstance(tile, FloorTile)
        self.assertIsInstance(tile, Tile)

    def test_door_tile_inheritance(self):
        """Test that DoorTile inherits from CorridorFloorTile."""
        tile = DoorTile(corridorix=0, doorix=0)
        self.assertIsInstance(tile, CorridorFloorTile)
        self.assertIsInstance(tile, FloorTile)
        self.assertIsInstance(tile, Tile)

    def test_secret_door_tile_inheritance(self):
        """Test that SecretDoorTile inherits from DoorTile."""
        tile = SecretDoorTile(corridorix=0, doorix=0)
        self.assertIsInstance(tile, DoorTile)
        self.assertIsInstance(tile, CorridorFloorTile)

    def test_chest_tile_inheritance(self):
        """Test that ChestTile inherits from RoomFloorTile."""
        tile = ChestTile(roomix=0)
        self.assertIsInstance(tile, RoomFloorTile)
        self.assertIsInstance(tile, FloorTile)

    def test_bookshelf_tile_inheritance(self):
        """Test that BookshelfTile inherits from ChestTile."""
        tile = BookshelfTile(roomix=0)
        self.assertIsInstance(tile, ChestTile)
        self.assertIsInstance(tile, RoomFloorTile)

    def test_mimic_tile_inheritance(self):
        """Test that MimicTile inherits from ChestTile."""
        tile = MimicTile(roomix=0, monster=MagicMock())
        self.assertIsInstance(tile, ChestTile)
        self.assertIsInstance(tile, RoomFloorTile)

    def test_ladder_tiles_inheritance(self):
        """Test that Ladder tiles inherit from RoomFloorTile."""
        up = LadderUpTile(roomix=0)
        down = LadderDownTile(roomix=0)
        self.assertIsInstance(up, RoomFloorTile)
        self.assertIsInstance(down, RoomFloorTile)

    def test_water_tile_inheritance(self):
        """Test that WaterTile inherits from Tile."""
        tile = WaterTile()
        self.assertIsInstance(tile, Tile)


class TestTileTypeChecking(unittest.TestCase):
    """Test type checking methods across different tile types."""

    def test_is_move_blocking_by_type(self):
        """Test is_move_blocking for different tile types."""
        # Should block
        self.assertTrue(WallTile().is_move_blocking())
        self.assertTrue(DoorTile(0, 0).is_move_blocking())
        self.assertTrue(ChestTile(0).is_move_blocking())
        self.assertTrue(LadderUpTile(0).is_move_blocking())
        self.assertTrue(LadderDownTile(0).is_move_blocking())
        self.assertTrue(WaterTile().is_move_blocking())
        # Should not block
        self.assertFalse(FloorTile().is_move_blocking())
        self.assertFalse(RoomFloorTile(0).is_move_blocking())
        self.assertFalse(CorridorFloorTile(0).is_move_blocking())
        self.assertFalse(BookshelfTile(0).is_move_blocking())

    def test_is_feature_by_type(self):
        """Test is_feature for different tile types."""
        # Should be features
        self.assertTrue(ChestTile(0).is_feature())
        self.assertTrue(BookshelfTile(0).is_feature())
        self.assertTrue(MimicTile(0, MagicMock()).is_feature())
        # Should not be features
        self.assertFalse(WallTile().is_feature())
        self.assertFalse(FloorTile().is_feature())
        self.assertFalse(RoomFloorTile(0).is_feature())
        self.assertFalse(DoorTile(0, 0).is_feature())

    def test_blocks_line_of_sight_by_type(self):
        """Test blocks_line_of_sight for different tile types."""
        # Should block
        self.assertTrue(WallTile().blocks_line_of_sight())
        self.assertTrue(DoorTile(0, 0).blocks_line_of_sight())
        # Should not block
        self.assertFalse(FloorTile().blocks_line_of_sight())
        self.assertFalse(RoomFloorTile(0).blocks_line_of_sight())
        self.assertFalse(WaterTile().blocks_line_of_sight())

    def test_is_ladder_by_type(self):
        """Test is_ladder for different tile types."""
        # Should be ladders
        self.assertTrue(LadderUpTile(0).is_ladder())
        self.assertTrue(LadderDownTile(0).is_ladder())
        # Should not be ladders
        self.assertFalse(WallTile().is_ladder())
        self.assertFalse(RoomFloorTile(0).is_ladder())
        self.assertFalse(ChestTile(0).is_ladder())


class TestRotYAwayFromWall(unittest.TestCase):
    """Test rotY_away_from_wall utility function."""

    def test_rotY_away_from_wall_with_wall(self):
        """Test rotY_away_from_wall when wall is nearby."""
        # Create mock dungeon floor with wall tiles
        df = MagicMock()
        # Set up tiles so that there's a wall neighbor
        df.tiles = {}
        for x in range(4, 8):
            df.tiles[x] = {}
            for y in range(4, 8):
                # Put a wall to the left of position (6, 5)
                if x == 5 and y == 5:
                    df.tiles[x][y] = WallTile()
                else:
                    df.tiles[x][y] = FloorTile()

        # Check position (6, 5) - wall is to the left at (5, 5)
        result = rotY_away_from_wall(df, 6, 5, original=0)
        self.assertIsNotNone(result)
        # Result should be one of the possible rotations
        self.assertIn(result, [0, 90, 180, 270])

    def test_rotY_away_from_wall_no_walls_nearby(self):
        """Test rotY_away_from_wall when no walls nearby."""
        df = MagicMock()
        # Create a grid with all floor tiles
        df.tiles = {
            4: {4: FloorTile(), 5: FloorTile(), 6: FloorTile()},
            5: {4: FloorTile(), 5: FloorTile(), 6: FloorTile()},
            6: {4: FloorTile(), 5: FloorTile(), 6: FloorTile()},
        }

        # Should return None when no walls found
        result = rotY_away_from_wall(df, 5, 5, original=0)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
