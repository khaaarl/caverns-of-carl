"""Unit tests for lib/corridors.py"""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from lib.corridors import CavernousCorridor, Corridor, CorridorWalker, Door


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
from lib.dungeon import DungeonFloor
from lib.room import RectRoom
from lib.tile import CorridorFloorTile, DoorTile, WallTile


def _make_dungeon_with_two_rooms(
    room1_x=10, room1_y=10, room2_x=20, room2_y=20, rw=2, rh=2
):
    """Create a DungeonFloor with two rooms for corridor testing."""
    config = DungeonConfig()
    df = DungeonFloor(config)
    room1 = RectRoom(room1_x, room1_y, rw=rw, rh=rh)
    room2 = RectRoom(room2_x, room2_y, rw=rw, rh=rh)
    df.add_room(room1)
    df.add_room(room2)
    return df, room1, room2


def _make_corridor(
    room1ix=0,
    room2ix=1,
    x1=10,
    y1=10,
    x2=20,
    y2=20,
    is_horizontal_first=True,
    width=1,
    biome_name=None,
    force_trivial=False,
):
    """Create a Corridor with reasonable defaults."""
    return Corridor(
        room1ix,
        room2ix,
        x1,
        y1,
        x2,
        y2,
        is_horizontal_first,
        width=width,
        biome_name=biome_name,
        force_trivial=force_trivial,
    )


def _make_door(door_type="Simple Wooden Door", corridor=None, **kwargs):
    """Create a Door with reasonable defaults."""
    if corridor is None:
        corridor = _make_corridor()
        corridor.ix = 0
    return Door(
        door_type, corridor, kwargs.pop("x", 15), kwargs.pop("y", 10), **kwargs
    )


# ---------------------------------------------------------------------------
# CorridorWalker tests
# ---------------------------------------------------------------------------
class TestCorridorWalker(unittest.TestCase):
    def test_walker_is_iterator(self):
        corridor = _make_corridor(x1=5, y1=5, x2=10, y2=5)
        walker = CorridorWalker(corridor)
        self.assertIs(iter(walker), walker)

    def test_walker_horizontal_straight_line(self):
        corridor = _make_corridor(
            x1=5, y1=5, x2=10, y2=5, is_horizontal_first=True, width=1
        )
        coords = list(corridor.walk())
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        # All y should be 5, x should go from 6 to 10
        self.assertTrue(all(y == 5 for y in ys))
        self.assertEqual(xs[0], 6)
        self.assertEqual(xs[-1], 10)

    def test_walker_vertical_straight_line(self):
        corridor = _make_corridor(
            x1=5, y1=5, x2=5, y2=10, is_horizontal_first=False, width=1
        )
        coords = list(corridor.walk())
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        self.assertTrue(all(x == 5 for x in xs))
        self.assertEqual(ys[0], 6)
        self.assertEqual(ys[-1], 10)

    def test_walker_l_shape_horizontal_first(self):
        corridor = _make_corridor(
            x1=5, y1=5, x2=10, y2=10, is_horizontal_first=True, width=1
        )
        coords = list(corridor.walk())
        # First leg goes horizontal (x changes), then vertical (y changes)
        # Should reach (10, 5) then go up to (10, 10)
        self.assertEqual(coords[-1], (10, 10))
        # Check that at some point x=10, y=5 is visited
        self.assertIn((10, 5), coords)

    def test_walker_l_shape_vertical_first(self):
        corridor = _make_corridor(
            x1=5, y1=5, x2=10, y2=10, is_horizontal_first=False, width=1
        )
        coords = list(corridor.walk())
        self.assertEqual(coords[-1], (10, 10))
        # Check that at some point x=5, y=10 is visited
        self.assertIn((5, 10), coords)

    def test_walker_negative_direction(self):
        corridor = _make_corridor(
            x1=10, y1=10, x2=5, y2=5, is_horizontal_first=True, width=1
        )
        coords = list(corridor.walk())
        self.assertEqual(coords[-1], (5, 5))

    def test_walker_width_2_yields_more_coords(self):
        corridor = _make_corridor(
            x1=5, y1=5, x2=10, y2=5, is_horizontal_first=True, width=2
        )
        coords_w1 = list(corridor.walk(max_width_iter=1))
        coords_w2 = list(corridor.walk(max_width_iter=2))
        self.assertGreater(len(coords_w2), len(coords_w1))

    def test_walker_max_width_iter_limits_output(self):
        corridor = _make_corridor(
            x1=5, y1=5, x2=10, y2=5, is_horizontal_first=True, width=3
        )
        coords_1 = list(corridor.walk(max_width_iter=1))
        coords_3 = list(corridor.walk(max_width_iter=3))
        self.assertLess(len(coords_1), len(coords_3))

    def test_walker_stopiteration_when_exhausted(self):
        corridor = _make_corridor(
            x1=5, y1=5, x2=7, y2=5, is_horizontal_first=True, width=1
        )
        walker = CorridorWalker(corridor)
        coords = list(walker)
        # After exhaustion, calling next should raise StopIteration
        with self.assertRaises(StopIteration):
            next(walker)

    def test_walker_same_start_end_single_step(self):
        """When start and end are adjacent, walker still produces coords."""
        corridor = _make_corridor(
            x1=5, y1=5, x2=6, y2=5, is_horizontal_first=True, width=1
        )
        coords = list(corridor.walk())
        self.assertEqual(len(coords), 1)
        self.assertEqual(coords[0], (6, 5))


# ---------------------------------------------------------------------------
# Corridor tests
# ---------------------------------------------------------------------------
class TestCorridorInit(unittest.TestCase):
    def test_corridor_stores_attributes(self):
        c = _make_corridor(
            room1ix=0,
            room2ix=1,
            x1=5,
            y1=5,
            x2=15,
            y2=15,
            width=2,
            biome_name="cave",
        )
        self.assertEqual(c.room1ix, 0)
        self.assertEqual(c.room2ix, 1)
        self.assertEqual(c.x1, 5)
        self.assertEqual(c.y1, 5)
        self.assertEqual(c.x2, 15)
        self.assertEqual(c.y2, 15)
        self.assertEqual(c.width, 2)
        self.assertEqual(c.biome_name, "cave")
        self.assertEqual(c.light_level, "bright")
        self.assertIsNone(c.ix)
        self.assertEqual(c.doorixs, set())
        self.assertEqual(c.trapixs, set())
        self.assertIsNone(c.name)
        self.assertFalse(c.force_trivial)

    def test_corridor_tile_style_dungeon(self):
        c = _make_corridor()
        self.assertEqual(c.tile_style(), "dungeon")

    def test_corridor_walk_returns_walker(self):
        c = _make_corridor()
        walker = c.walk()
        self.assertIsInstance(walker, CorridorWalker)

    def test_corridor_is_fully_enclosed_no_doors(self):
        c = _make_corridor()
        self.assertFalse(c.is_fully_enclosed_by_doors())

    def test_corridor_is_fully_enclosed_one_door(self):
        c = _make_corridor()
        c.doorixs = {0}
        self.assertFalse(c.is_fully_enclosed_by_doors())

    def test_corridor_is_fully_enclosed_two_doors(self):
        c = _make_corridor()
        c.doorixs = {0, 1}
        self.assertTrue(c.is_fully_enclosed_by_doors())


class TestCorridorWithDungeon(unittest.TestCase):
    """Tests that require a DungeonFloor with rooms and an added corridor."""

    def setUp(self):
        self.df, self.room1, self.room2 = _make_dungeon_with_two_rooms()
        corridor = _make_corridor(
            room1ix=0,
            room2ix=1,
            x1=self.room1.x,
            y1=self.room1.y,
            x2=self.room2.x,
            y2=self.room2.y,
            is_horizontal_first=True,
            width=1,
        )
        self.df.add_corridor(corridor)
        self.corridor = self.df.corridors[0]

    def test_add_corridor_sets_ix(self):
        self.assertEqual(self.corridor.ix, 0)

    def test_add_corridor_creates_floor_tiles(self):
        has_corridor_tile = False
        for x, y in self.corridor.walk():
            tile = self.df.tiles[x][y]
            if isinstance(tile, CorridorFloorTile):
                has_corridor_tile = True
                break
        self.assertTrue(has_corridor_tile)

    def test_tile_coords_yields_corridor_tiles(self):
        coords = list(self.corridor.tile_coords(self.df))
        self.assertGreater(len(coords), 0)
        for x, y in coords:
            tile = self.df.tiles[x][y]
            self.assertIsInstance(tile, CorridorFloorTile)

    def test_tile_coords_exclude_doors_by_default(self):
        # Place a door tile manually
        walk_coords = list(self.corridor.walk(max_width_iter=1))
        for x, y in walk_coords:
            if isinstance(self.df.tiles[x][y], CorridorFloorTile):
                self.df.tiles[x][y] = DoorTile(
                    self.corridor.ix, biome_name=None
                )
                self.df.tiles[x][y].x = x
                self.df.tiles[x][y].y = y
                break
        coords_no_doors = list(self.corridor.tile_coords(self.df))
        coords_with_doors = list(
            self.corridor.tile_coords(self.df, include_doors=True)
        )
        self.assertLess(len(coords_no_doors), len(coords_with_doors))

    def test_length_positive(self):
        length = self.corridor.length(self.df)
        self.assertGreater(length, 0)

    def test_is_nontrivial_long_corridor(self):
        # Our rooms are 10 apart, should be nontrivial
        self.assertTrue(self.corridor.is_nontrivial(self.df))

    def test_is_trivial_inverse(self):
        self.assertNotEqual(
            self.corridor.is_trivial(self.df),
            self.corridor.is_nontrivial(self.df),
        )

    def test_force_trivial_overrides(self):
        df, r1, r2 = _make_dungeon_with_two_rooms()
        corridor = _make_corridor(
            room1ix=0,
            room2ix=1,
            x1=r1.x,
            y1=r1.y,
            x2=r2.x,
            y2=r2.y,
            force_trivial=True,
        )
        df.add_corridor(corridor)
        self.assertFalse(corridor.is_nontrivial(df))
        self.assertTrue(corridor.is_trivial(df))

    def test_middle_coords_inside_corridor(self):
        mx, my = self.corridor.middle_coords(self.df)
        tile = self.df.tiles[mx][my]
        self.assertIsInstance(tile, CorridorFloorTile)

    def test_middle_coords_raises_on_no_tiles(self):
        """Corridor that has no floor tiles raises RuntimeError."""
        # Create a corridor that doesn't overlap any floor tiles
        corridor = _make_corridor(x1=1, y1=1, x2=2, y2=1, width=1)
        corridor.ix = 99
        # Don't add it to dungeon (tiles stay WallTile)
        with self.assertRaises(RuntimeError):
            corridor.middle_coords(self.df)

    def test_door_coords_empty_when_no_doors(self):
        coords = self.corridor.door_coords(self.df)
        self.assertEqual(coords, [])

    def test_door_coords_finds_door_tiles(self):
        # Place a door tile on the corridor
        for x, y in self.corridor.walk(max_width_iter=1):
            if isinstance(self.df.tiles[x][y], CorridorFloorTile):
                dt = DoorTile(self.corridor.ix, biome_name=None)
                dt.x = x
                dt.y = y
                self.df.tiles[x][y] = dt
                break
        coords = self.corridor.door_coords(self.df)
        self.assertEqual(len(coords), 1)

    def test_description_includes_light_level(self):
        self.corridor.light_level = "dim"
        self.corridor.name = "C1"
        doc = self.corridor.description(self.df, verbose=False)
        text = doc.flat_body().unstyled()
        self.assertIn("Dim", text)

    def test_tts_fog_bits_nonempty(self):
        fogs = self.corridor.tts_fog_bits(self.df)
        self.assertGreater(len(fogs), 0)

    def test_tts_fog_bits_empty_when_all_doors(self):
        """If every corridor tile is a DoorTile, fog bits should be empty."""
        for x, y in self.corridor.walk():
            tile = self.df.tiles[x][y]
            if isinstance(tile, CorridorFloorTile) and not isinstance(
                tile, DoorTile
            ):
                dt = DoorTile(self.corridor.ix, biome_name=None)
                dt.x = x
                dt.y = y
                dt.corridorix = self.corridor.ix
                self.df.tiles[x][y] = dt
        fogs = self.corridor.tts_fog_bits(self.df)
        self.assertEqual(fogs, [])

    def test_tts_fog_bits_skip_river_tiles(self):
        """Tiles with riverixs should be skipped."""
        # Add a riverix to all corridor tiles
        for x, y in self.corridor.walk():
            tile = self.df.tiles[x][y]
            if isinstance(tile, CorridorFloorTile):
                tile.riverixs.add(0)
        fogs = self.corridor.tts_fog_bits(self.df)
        self.assertEqual(fogs, [])


class TestCorridorShortPath(unittest.TestCase):
    """Test corridor behavior when rooms are very close together."""

    def test_short_corridor_is_trivial(self):
        df, r1, r2 = _make_dungeon_with_two_rooms(
            room1_x=10, room1_y=10, room2_x=13, room2_y=10, rw=1, rh=1
        )
        corridor = _make_corridor(
            room1ix=0,
            room2ix=1,
            x1=r1.x,
            y1=r1.y,
            x2=r2.x,
            y2=r2.y,
            width=1,
        )
        df.add_corridor(corridor)
        # Rooms 3 apart with rw=1 means very short corridor
        self.assertFalse(corridor.is_nontrivial(df))

    def test_wide_corridor_nontrivial_threshold(self):
        """Width-3 corridor divides usable_length by 3."""
        df, r1, r2 = _make_dungeon_with_two_rooms(
            room1_x=10, room1_y=10, room2_x=20, room2_y=10, rw=2, rh=2
        )
        corridor = _make_corridor(
            room1ix=0,
            room2ix=1,
            x1=r1.x,
            y1=r1.y,
            x2=r2.x,
            y2=r2.y,
            width=3,
        )
        df.add_corridor(corridor)
        # With width=3, each tile counts as 1/3
        # The length is divided by width, so needs more tiles to be nontrivial
        length = corridor.length(df)
        self.assertGreater(length, 0)


# ---------------------------------------------------------------------------
# CavernousCorridor tests
# ---------------------------------------------------------------------------
class TestCavernousCorridor(unittest.TestCase):
    def test_tile_style_cavern(self):
        c = CavernousCorridor(0, 1, 5, 5, 15, 15, True)
        self.assertEqual(c.tile_style(), "cavern")

    def test_never_enclosed_by_doors(self):
        c = CavernousCorridor(0, 1, 5, 5, 15, 15, True)
        self.assertFalse(c.is_fully_enclosed_by_doors())

    def test_never_enclosed_even_with_doorixs(self):
        c = CavernousCorridor(0, 1, 5, 5, 15, 15, True)
        c.doorixs = {0, 1, 2}
        self.assertFalse(c.is_fully_enclosed_by_doors())

    def test_inherits_walk(self):
        c = CavernousCorridor(0, 1, 5, 5, 15, 15, True, width=1)
        walker = c.walk()
        self.assertIsInstance(walker, CorridorWalker)
        coords = list(walker)
        self.assertGreater(len(coords), 0)


# ---------------------------------------------------------------------------
# Door tests
# ---------------------------------------------------------------------------
class TestDoorInit(unittest.TestCase):
    def test_door_stores_attributes(self):
        corridor = _make_corridor()
        corridor.ix = 5
        door = Door(
            "Iron Door",
            corridor,
            x=10,
            y=15,
            lock_dc=18,
            biome_name="dungeon",
            is_secret=True,
            detection_dc=16,
        )
        self.assertEqual(door.door_type, "Iron Door")
        self.assertEqual(door.x, 10)
        self.assertEqual(door.y, 15)
        self.assertEqual(door.corridorix, 5)
        self.assertEqual(door.width, 1)
        self.assertEqual(door.lock_dc, 18)
        self.assertEqual(door.biome_name, "dungeon")
        self.assertTrue(door.is_secret)
        self.assertEqual(door.detection_dc, 16)
        self.assertEqual(door.roomixs, set())
        self.assertEqual(door.trapixs, set())
        self.assertIsNone(door.ix)

    def test_door_default_roomixs_empty(self):
        door = _make_door()
        self.assertEqual(door.roomixs, set())

    def test_door_roomixs_from_list(self):
        door = _make_door(roomixs=[0, 1])
        self.assertEqual(door.roomixs, {0, 1})


class TestDoorStats(unittest.TestCase):
    """Test door physical stats from the type table."""

    def test_crude_wooden_stats(self):
        door = _make_door("Crude Wooden Door")
        self.assertEqual(door.thickness(), 1)
        self.assertEqual(door.damage_threshold(), 0)
        self.assertEqual(door.armor_class(), 15)
        self.assertEqual(door.health(), 10)

    def test_simple_wooden_stats(self):
        door = _make_door("Simple Wooden Door")
        self.assertEqual(door.thickness(), 2)
        self.assertEqual(door.damage_threshold(), 0)
        self.assertEqual(door.armor_class(), 15)
        self.assertEqual(door.health(), 15)

    def test_heavy_wooden_stats(self):
        door = _make_door("Heavy Wooden Door")
        self.assertEqual(door.thickness(), 4)
        self.assertEqual(door.damage_threshold(), 10)
        self.assertEqual(door.armor_class(), 15)
        self.assertEqual(door.health(), 25)

    def test_reinforced_wooden_stats(self):
        door = _make_door("Reinforced Wooden Door")
        self.assertEqual(door.thickness(), 4)
        self.assertEqual(door.damage_threshold(), 15)
        self.assertEqual(door.armor_class(), 17)
        self.assertEqual(door.health(), 40)

    def test_stone_stats(self):
        door = _make_door("Stone Door")
        self.assertEqual(door.thickness(), 4)
        self.assertEqual(door.damage_threshold(), 25)
        self.assertEqual(door.armor_class(), 17)
        self.assertEqual(door.health(), 60)

    def test_iron_stats(self):
        door = _make_door("Iron Door")
        self.assertEqual(door.thickness(), 2)
        self.assertEqual(door.damage_threshold(), 30)
        self.assertEqual(door.armor_class(), 19)
        self.assertEqual(door.health(), 100)


class TestDoorNickname(unittest.TestCase):
    def test_simple_small_door(self):
        corridor = _make_corridor(width=1)
        corridor.ix = 0
        door = Door("Simple Wooden Door", corridor, 5, 5)
        self.assertEqual(door.nickname(), "Small Simple Wooden Door")

    def test_large_door(self):
        corridor = _make_corridor(width=2)
        corridor.ix = 0
        door = Door("Heavy Wooden Door", corridor, 5, 5)
        self.assertEqual(door.nickname(), "Large Heavy Wooden Door")

    def test_huge_door(self):
        corridor = _make_corridor(width=3)
        corridor.ix = 0
        door = Door("Stone Door", corridor, 5, 5)
        self.assertEqual(door.nickname(), "Huge Stone Door")

    def test_locked_prefix(self):
        corridor = _make_corridor(width=1)
        corridor.ix = 0
        door = Door("Iron Door", corridor, 5, 5, lock_dc=15)
        self.assertIn("Locked", door.nickname())

    def test_secret_prefix(self):
        corridor = _make_corridor(width=1)
        corridor.ix = 0
        door = Door("Iron Door", corridor, 5, 5, is_secret=True)
        self.assertIn("Secret", door.nickname())

    def test_secret_locked_both_prefixes(self):
        corridor = _make_corridor(width=1)
        corridor.ix = 0
        door = Door("Iron Door", corridor, 5, 5, lock_dc=15, is_secret=True)
        nick = door.nickname()
        self.assertTrue(nick.startswith("Secret Locked"))


class TestDoorTTSMethods(unittest.TestCase):
    def test_tts_nickname_normal_door(self):
        door = _make_door("Simple Wooden Door")
        nick = door.tts_nickname()
        self.assertIn("15/15", nick)
        self.assertIn("Simple Wooden Door", nick)

    def test_tts_nickname_secret_door_is_empty(self):
        door = _make_door("Simple Wooden Door", is_secret=True)
        self.assertEqual(door.tts_nickname(), "")

    def test_tts_description_normal_door(self):
        door = _make_door("Iron Door")
        desc = door.tts_description()
        self.assertIn("Armor Class: 19", desc)
        self.assertIn("Damage Threshold: 30", desc)

    def test_tts_description_secret_door_is_empty(self):
        door = _make_door("Iron Door", is_secret=True)
        self.assertEqual(door.tts_description(), "")

    def test_tts_gmnotes_secret_door(self):
        door = _make_door(is_secret=True, detection_dc=14)
        df = MagicMock()
        notes = door.tts_gmnotes(df)
        self.assertIn("Secret Door!", notes)
        self.assertIn("14", notes)

    def test_tts_gmnotes_locked_door(self):
        door = _make_door(lock_dc=16)
        df = MagicMock()
        notes = door.tts_gmnotes(df)
        self.assertIn("Lock DC: 16", notes)

    def test_tts_gmnotes_with_trap(self):
        door = _make_door()
        door.trapixs = {0}
        mock_trap = MagicMock()
        mock_trap.description.return_value = "Poison dart trap"
        df = MagicMock()
        df.traps = {0: mock_trap}
        notes = door.tts_gmnotes(df)
        self.assertIn("Poison dart trap", notes)

    def test_tts_gmnotes_combined(self):
        door = _make_door(is_secret=True, detection_dc=14, lock_dc=16)
        door.trapixs = {0}
        mock_trap = MagicMock()
        mock_trap.description.return_value = "Blade trap"
        df = MagicMock()
        df.traps = {0: mock_trap}
        notes = door.tts_gmnotes(df)
        self.assertIn("Secret Door!", notes)
        self.assertIn("Lock DC: 16", notes)
        self.assertIn("Blade trap", notes)


class TestDoorMinimumStrength(unittest.TestCase):
    def test_upgrade_weak_to_strong(self):
        door = _make_door("Crude Wooden Door")
        door.apply_minimum_door_strength("Stone Door")
        self.assertEqual(door.door_type, "Stone Door")

    def test_no_downgrade(self):
        door = _make_door("Stone Door")
        door.apply_minimum_door_strength("Simple Wooden Door")
        self.assertEqual(door.door_type, "Stone Door")

    def test_same_type_no_change(self):
        door = _make_door("Heavy Wooden Door")
        door.apply_minimum_door_strength("Heavy Wooden Door")
        self.assertEqual(door.door_type, "Heavy Wooden Door")

    def test_upgrade_to_iron(self):
        door = _make_door("Crude Wooden Door")
        door.apply_minimum_door_strength("Iron Door")
        self.assertEqual(door.door_type, "Iron Door")


class TestDoorPickType(unittest.TestCase):
    @patch("lib.corridors.eval_dice")
    def test_pick_type_low_level(self, mock_dice):
        mock_dice.return_value = 1
        config = MagicMock()
        config.target_character_level = 1
        door_type = Door.pick_type(config)
        self.assertIn(door_type, [t[0] for t in Door.door_type_table])

    @patch("lib.corridors.eval_dice")
    def test_pick_type_high_level(self, mock_dice):
        mock_dice.return_value = 20
        config = MagicMock()
        config.target_character_level = 20
        door_type = Door.pick_type(config)
        # Should be near the top of the table
        self.assertIn(door_type, [t[0] for t in Door.door_type_table])

    @patch("lib.corridors.eval_dice")
    def test_pick_type_clamped(self, mock_dice):
        mock_dice.return_value = 20
        config = MagicMock()
        config.target_character_level = 100
        door_type = Door.pick_type(config)
        # Should not exceed table bounds
        self.assertEqual(door_type, Door.door_type_table[-1][0])


class TestDoorTypeTable(unittest.TestCase):
    def test_table_has_six_entries(self):
        self.assertEqual(len(Door.door_type_table), 6)

    def test_first_entry_is_crude(self):
        self.assertEqual(Door.door_type_table[0][0], "Crude Wooden Door")

    def test_last_entry_is_iron(self):
        self.assertEqual(Door.door_type_table[-1][0], "Iron Door")

    def test_dict_matches_table(self):
        for name, thickness, threshold, ac, hp in Door.door_type_table:
            self.assertIn(name, Door.door_type_dict)
            d = Door.door_type_dict[name]
            self.assertEqual(d["thickness"], thickness)
            self.assertEqual(d["threshold"], threshold)
            self.assertEqual(d["ac"], ac)
            self.assertEqual(d["hp"], hp)

    def test_dict_keys_match_table_names(self):
        table_names = {t[0] for t in Door.door_type_table}
        dict_names = set(Door.door_type_dict.keys())
        self.assertEqual(table_names, dict_names)


if __name__ == "__main__":
    unittest.main()
