"""Unit tests for lib/features.py"""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from lib.features import (
    Altar,
    Blacksmith,
    Deity,
    SpecialFeature,
    deity_library,
)
from lib.tile import CorridorFloorTile, RoomFloorTile, WallTile


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
        ttk_mock.Notebook = MagicMock()
        ttk_mock.Frame = MagicMock()
        ttk_mock.Style = MagicMock()

        tk_mock.ttk = ttk_mock
        sys.modules["tkinter"] = tk_mock
        sys.modules["tkinter.ttk"] = ttk_mock


mock_tkinter()


# --- Helper factories ---


def _make_room(
    ix=0,
    trivial=False,
    biome_name="default",
    tile_style="dungeon",
    enclosed=True,
    light_level="bright",
    total_space=9,
    has_ladder=False,
    doorixs=None,
):
    """Create a mock room with controllable properties."""
    room = MagicMock()
    room.ix = ix
    room.biome_name = biome_name
    room.is_trivial.return_value = trivial
    room.tile_style.return_value = tile_style
    room.is_fully_enclosed_by_doors.return_value = enclosed
    room.light_level = light_level
    room.total_space.return_value = total_space
    room.has_ladder.return_value = has_ladder
    room.doorixs = doorixs or []
    return room


def _make_df(rooms=None):
    """Create a mock DungeonFloor with rooms."""
    df = MagicMock()
    df.rooms = rooms or []
    return df


# --- SpecialFeature base class ---


class TestSpecialFeatureInit(unittest.TestCase):
    """Test SpecialFeature.__init__ and defaults."""

    @patch("random.random", return_value=0.42)
    def test_stores_biome_name(self, _mock_rand):
        sf = SpecialFeature(biome_name="cavern")
        self.assertEqual(sf.biome_name, "cavern")

    @patch("random.random", return_value=0.42)
    def test_default_biome_name_none(self, _mock_rand):
        sf = SpecialFeature()
        self.assertIsNone(sf.biome_name)

    @patch("random.random", return_value=0.42)
    def test_roomix_starts_none(self, _mock_rand):
        sf = SpecialFeature()
        self.assertIsNone(sf.roomix)

    @patch("random.random", return_value=0.42)
    def test_rand_stored(self, _mock_rand):
        sf = SpecialFeature()
        self.assertAlmostEqual(sf.rand, 0.42)


class TestSpecialFeatureDefaults(unittest.TestCase):
    """Test SpecialFeature default method returns."""

    @patch("random.random", return_value=0.5)
    def test_allows_enemies_false(self, _):
        self.assertFalse(SpecialFeature().allows_enemies())

    @patch("random.random", return_value=0.5)
    def test_allows_other_features_false(self, _):
        self.assertFalse(SpecialFeature().allows_other_features())

    @patch("random.random", return_value=0.5)
    def test_allows_treasure_false(self, _):
        self.assertFalse(SpecialFeature().allows_treasure())

    @patch("random.random", return_value=0.5)
    def test_allows_traps_false(self, _):
        self.assertFalse(SpecialFeature().allows_traps())

    @patch("random.random", return_value=0.5)
    def test_tts_handouts_empty(self, _):
        self.assertEqual(SpecialFeature().tts_handouts(), [])

    @patch("random.random", return_value=0.5)
    def test_description_raises(self, _):
        with self.assertRaises(NotImplementedError):
            SpecialFeature().description(None)

    @patch("random.random", return_value=0.5)
    def test_tts_objects_raises(self, _):
        with self.assertRaises(NotImplementedError):
            SpecialFeature().tts_objects(None)

    @patch("random.random", return_value=0.5)
    def test_ascii_chars_raises(self, _):
        with self.assertRaises(NotImplementedError):
            SpecialFeature().ascii_chars(None)

    @patch("random.random", return_value=0.5)
    def test_score_room_returns_1(self, _):
        self.assertEqual(SpecialFeature().score_room(None, None), 1.0)

    @patch("random.random", return_value=0.5)
    def test_mod_tts_room_tile_returns_none(self, _):
        self.assertIsNone(SpecialFeature().mod_tts_room_tile({}))

    @patch("random.random", return_value=0.5)
    def test_post_process_returns_none(self, _):
        self.assertIsNone(SpecialFeature().post_process(None))


class TestSpecialFeatureScoreRooms(unittest.TestCase):
    """Test SpecialFeature.score_rooms() filtering logic."""

    @patch("random.random", return_value=0.5)
    def test_skips_trivial_rooms(self, _):
        sf = SpecialFeature()
        room = _make_room(ix=0, trivial=True)
        df = _make_df(rooms=[room])
        self.assertEqual(sf.score_rooms(df), {})

    @patch("random.random", return_value=0.5)
    def test_includes_nontrivial_rooms(self, _):
        sf = SpecialFeature()
        room = _make_room(ix=0, trivial=False)
        df = _make_df(rooms=[room])
        scores = sf.score_rooms(df)
        self.assertIn(0, scores)
        self.assertGreater(scores[0], 0)

    @patch("random.random", return_value=0.5)
    def test_filters_by_biome_name(self, _):
        sf = SpecialFeature(biome_name="cavern")
        room_match = _make_room(ix=0, biome_name="cavern")
        room_other = _make_room(ix=1, biome_name="dungeon")
        df = _make_df(rooms=[room_match, room_other])
        scores = sf.score_rooms(df)
        self.assertIn(0, scores)
        self.assertNotIn(1, scores)

    @patch("random.random", return_value=0.5)
    def test_no_biome_filter_includes_all(self, _):
        sf = SpecialFeature()
        room_a = _make_room(ix=0, biome_name="cavern")
        room_b = _make_room(ix=1, biome_name="dungeon")
        df = _make_df(rooms=[room_a, room_b])
        scores = sf.score_rooms(df)
        self.assertIn(0, scores)
        self.assertIn(1, scores)

    @patch("random.random", return_value=0.5)
    def test_excludes_rooms_with_zero_score(self, _):
        sf = SpecialFeature()
        sf.score_room = lambda df, room: 0.0
        room = _make_room(ix=0)
        df = _make_df(rooms=[room])
        self.assertEqual(sf.score_rooms(df), {})

    @patch("random.random", return_value=0.5)
    def test_excludes_rooms_with_negative_score(self, _):
        sf = SpecialFeature()
        sf.score_room = lambda df, room: -1.0
        room = _make_room(ix=0)
        df = _make_df(rooms=[room])
        self.assertEqual(sf.score_rooms(df), {})


# --- Deity ---


class TestDeity(unittest.TestCase):
    """Test Deity data class initialization."""

    def _make_deity_blob(self, **overrides):
        blob = {
            "Name": "TestGod",
            "FullTitle": "TestGod, The Great",
            "TTSAltarNickname": "Test Altar",
            "AltarDescriptions": ["A test altar."],
            "Requests": [{"Request": "Do something"}],
            "AsciiColor": "[1;91m",
        }
        blob.update(overrides)
        return blob

    def test_required_fields(self):
        blob = self._make_deity_blob()
        deity = Deity(blob)
        self.assertEqual(deity.name, "TestGod")
        self.assertEqual(deity.full_title, "TestGod, The Great")
        self.assertEqual(deity.tts_altar_nickname, "Test Altar")
        self.assertEqual(deity.altar_descriptions, ["A test altar."])
        self.assertEqual(deity.ascii_color, "[1;91m")

    def test_full_title_defaults_to_name(self):
        blob = self._make_deity_blob()
        del blob["FullTitle"]
        deity = Deity(blob)
        self.assertEqual(deity.full_title, "TestGod")

    def test_minimum_door_strength_optional(self):
        blob = self._make_deity_blob()
        deity = Deity(blob)
        self.assertIsNone(deity.minimum_door_strength)

    def test_minimum_door_strength_set(self):
        blob = self._make_deity_blob(MinimumDoorStrength="Stone Door")
        deity = Deity(blob)
        self.assertEqual(deity.minimum_door_strength, "Stone Door")

    def test_prefer_dark_defaults_false(self):
        blob = self._make_deity_blob()
        deity = Deity(blob)
        self.assertFalse(deity.prefer_dark)

    def test_prefer_dark_set(self):
        blob = self._make_deity_blob(PreferDark=True)
        deity = Deity(blob)
        self.assertTrue(deity.prefer_dark)

    def test_tts_tile_tint_optional(self):
        blob = self._make_deity_blob()
        deity = Deity(blob)
        self.assertIsNone(deity.tts_tile_tint)

    def test_tts_tile_tint_set(self):
        tint = {"r": 1.0, "g": 0.5, "b": 0.5}
        blob = self._make_deity_blob(TTSTileTint=tint)
        deity = Deity(blob)
        self.assertEqual(deity.tts_tile_tint, tint)


# --- deity_library ---


class TestDeityLibrary(unittest.TestCase):
    """Test the deity_library() function."""

    def setUp(self):
        # Clear the cache before each test
        deity_library.cache_clear()

    def test_returns_dict(self):
        lib = deity_library()
        self.assertIsInstance(lib, dict)

    def test_contains_known_deities(self):
        lib = deity_library()
        self.assertIn("Kryxix", lib)
        self.assertIn("Ssarthaxx", lib)

    def test_values_are_deity_objects(self):
        lib = deity_library()
        for name, deity in lib.items():
            self.assertIsInstance(deity, Deity)
            self.assertEqual(deity.name, name)

    def test_kryxix_prefers_dark(self):
        lib = deity_library()
        self.assertTrue(lib["Kryxix"].prefer_dark)

    def test_ssarthaxx_has_minimum_door_strength(self):
        lib = deity_library()
        self.assertEqual(lib["Ssarthaxx"].minimum_door_strength, "Stone Door")

    def test_cached(self):
        lib1 = deity_library()
        lib2 = deity_library()
        self.assertIs(lib1, lib2)


# --- Blacksmith ---


class TestBlacksmithDescription(unittest.TestCase):
    """Test Blacksmith.description()."""

    @patch("random.random", return_value=0.5)
    def test_description_mentions_andrus(self, _):
        bs = Blacksmith()
        desc = bs.description(None)
        self.assertIn("Andrus", desc)
        self.assertIn("Eastora", desc)


class TestBlacksmithScoreRoom(unittest.TestCase):
    """Test Blacksmith.score_room() scoring logic."""

    @patch("random.random", return_value=0.0)
    def test_prefers_dungeon_tile_style(self, _):
        bs = Blacksmith()
        room_dungeon = _make_room(tile_style="dungeon")
        room_cavern = _make_room(tile_style="cavern")
        df = _make_df()
        # Mock _thing_coords to always return valid coords
        bs._thing_coords = lambda df, room: {
            "smith_coords": (5, 5),
            "anvil_coords": (6, 5),
        }
        score_d = bs.score_room(df, room_dungeon)
        score_c = bs.score_room(df, room_cavern)
        self.assertGreater(score_d, score_c)

    @patch("random.random", return_value=0.0)
    def test_prefers_enclosed_rooms(self, _):
        bs = Blacksmith()
        room_enc = _make_room(enclosed=True)
        room_open = _make_room(enclosed=False)
        df = _make_df()
        bs._thing_coords = lambda df, room: {
            "smith_coords": (5, 5),
            "anvil_coords": (6, 5),
        }
        score_enc = bs.score_room(df, room_enc)
        score_open = bs.score_room(df, room_open)
        self.assertGreater(score_enc, score_open)

    @patch("random.random", return_value=0.0)
    def test_prefers_bright_rooms(self, _):
        bs = Blacksmith()
        room_bright = _make_room(light_level="bright")
        room_dark = _make_room(light_level="dark")
        df = _make_df()
        bs._thing_coords = lambda df, room: {
            "smith_coords": (5, 5),
            "anvil_coords": (6, 5),
        }
        score_b = bs.score_room(df, room_bright)
        score_d = bs.score_room(df, room_dark)
        self.assertGreater(score_b, score_d)

    @patch("random.random", return_value=0.0)
    def test_prefers_smaller_rooms(self, _):
        bs = Blacksmith()
        room_small = _make_room(total_space=9)
        room_big = _make_room(total_space=36)
        df = _make_df()
        bs._thing_coords = lambda df, room: {
            "smith_coords": (5, 5),
            "anvil_coords": (6, 5),
        }
        score_s = bs.score_room(df, room_small)
        score_b = bs.score_room(df, room_big)
        self.assertGreater(score_s, score_b)

    @patch("random.random", return_value=0.0)
    def test_negative_score_when_no_thing_coords(self, _):
        bs = Blacksmith()
        room = _make_room()
        df = _make_df()
        bs._thing_coords = lambda df, room: None
        score = bs.score_room(df, room)
        self.assertLess(score, 0)


class TestBlacksmithThingCoords(unittest.TestCase):
    """Test Blacksmith._thing_coords() placement logic."""

    @patch("random.random", return_value=0.0)
    def test_returns_none_when_no_valid_placement(self, _):
        bs = Blacksmith()
        room = MagicMock()
        # All tiles are blocking
        room.tile_coords.return_value = [(5, 5)]
        df = _make_df()
        blocking_tile = MagicMock()
        blocking_tile.is_move_blocking.return_value = True
        df.get_tile.return_value = blocking_tile
        result = bs._thing_coords(df, room)
        self.assertIsNone(result)

    @patch("random.random", return_value=0.0)
    def test_returns_dict_with_smith_and_anvil(self, _):
        bs = Blacksmith()
        room = MagicMock()
        room.tile_coords.return_value = [(5, 5), (6, 5), (5, 6)]

        df = _make_df()

        # smith tile at (5,5): not blocking, near wall, not near corridor
        smith_tile = RoomFloorTile(5, 5)
        wall_tile = WallTile(4, 5)
        # anvil tile at (6,5): not blocking, neighbors not blocking
        anvil_tile = RoomFloorTile(6, 5)
        floor_tile = RoomFloorTile(7, 5)

        def get_tile(x, y):
            tiles = {(5, 5): smith_tile, (6, 5): anvil_tile}
            return tiles.get((x, y), floor_tile)

        df.get_tile = get_tile

        def neighbor_tiles(tile, diagonal=False):
            if tile is smith_tile and not diagonal:
                return [wall_tile, anvil_tile]
            if tile is smith_tile and diagonal:
                return [wall_tile, anvil_tile]
            if tile is anvil_tile and not diagonal:
                return [smith_tile, floor_tile]
            if tile is anvil_tile and diagonal:
                return [smith_tile, floor_tile]
            return []

        df.neighbor_tiles = neighbor_tiles

        result = bs._thing_coords(df, room)
        self.assertIsNotNone(result)
        self.assertIn("smith_coords", result)
        self.assertIn("anvil_coords", result)

    @patch("random.random", return_value=0.0)
    def test_avoids_corridor_adjacent_tiles(self, _):
        bs = Blacksmith()
        room = MagicMock()
        room.tile_coords.return_value = [(5, 5)]

        df = _make_df()
        smith_tile = RoomFloorTile(5, 5)
        corridor_tile = CorridorFloorTile(4, 5)
        wall_tile = WallTile(6, 5)

        df.get_tile = lambda x, y: smith_tile

        def neighbor_tiles(tile, diagonal=False):
            if tile is smith_tile and not diagonal:
                return [wall_tile, corridor_tile]
            if tile is smith_tile and diagonal:
                return [wall_tile, corridor_tile]
            return []

        df.neighbor_tiles = neighbor_tiles
        result = bs._thing_coords(df, room)
        self.assertIsNone(result)


class TestBlacksmithAsciiChars(unittest.TestCase):
    """Test Blacksmith.ascii_chars()."""

    @patch("random.random", return_value=0.0)
    def test_returns_two_chars(self, _):
        bs = Blacksmith()
        bs.roomix = 0
        room = MagicMock()
        df = _make_df(rooms=[room])
        bs._thing_coords = lambda df, room: {
            "smith_coords": (3, 4),
            "anvil_coords": (4, 4),
        }
        chars = bs.ascii_chars(df)
        self.assertEqual(len(chars), 2)
        self.assertEqual(chars[0][:2], (3, 4))
        self.assertEqual(chars[1][:2], (4, 4))
        self.assertIn("&", chars[0][2])
        self.assertIn("]", chars[1][2])


# --- Altar ---


class TestAltarInit(unittest.TestCase):
    """Test Altar.__init__."""

    @patch("random.random", return_value=0.5)
    @patch("random.choice")
    def test_stores_deity_name(self, mock_choice, _):
        lib = deity_library()
        mock_choice.return_value = lib["Kryxix"].requests[0]
        altar = Altar("Kryxix")
        self.assertEqual(altar.deity_name, "Kryxix")

    @patch("random.random", return_value=0.5)
    @patch("random.choice")
    def test_stores_deity_object(self, mock_choice, _):
        lib = deity_library()
        mock_choice.return_value = lib["Kryxix"].requests[0]
        altar = Altar("Kryxix")
        self.assertIsInstance(altar.deity, Deity)
        self.assertEqual(altar.deity.name, "Kryxix")

    @patch("random.random", return_value=0.5)
    @patch("random.choice")
    def test_stores_altar_description(self, mock_choice, _):
        lib = deity_library()
        mock_choice.return_value = lib["Kryxix"].requests[0]
        altar = Altar("Kryxix")
        self.assertEqual(
            altar.altar_description, lib["Kryxix"].altar_descriptions[0]
        )

    @patch("random.random", return_value=0.5)
    @patch("random.choice")
    def test_stores_request(self, mock_choice, _):
        lib = deity_library()
        req = lib["Kryxix"].requests[0]
        mock_choice.return_value = req
        altar = Altar("Kryxix")
        self.assertIs(altar.request, req)


class TestAltarDescription(unittest.TestCase):
    """Test Altar.description()."""

    @patch("random.random", return_value=0.5)
    @patch("random.choice")
    def test_non_verbose_is_short(self, mock_choice, _):
        lib = deity_library()
        mock_choice.return_value = lib["Kryxix"].requests[0]
        altar = Altar("Kryxix")
        desc = altar.description(None, verbose=False)
        self.assertEqual(desc, "An altar to Kryxix")

    @patch("random.random", return_value=0.5)
    @patch("random.choice")
    def test_verbose_returns_doc(self, mock_choice, _):
        lib = deity_library()
        mock_choice.return_value = lib["Kryxix"].requests[0]
        altar = Altar("Kryxix")
        desc = altar.description(None, verbose=True)
        # Verbose returns a Doc object, not a string
        from lib.utils import Doc

        self.assertIsInstance(desc, Doc)


class TestAltarScoreRoom(unittest.TestCase):
    """Test Altar.score_room() scoring logic."""

    def _make_altar(self, deity_name="Ssarthaxx"):
        with patch("random.random", return_value=0.0), patch(
            "random.choice"
        ) as mock_choice:
            lib = deity_library()
            mock_choice.return_value = lib[deity_name].requests[0]
            altar = Altar(deity_name)
            altar._thing_coords = lambda df, room: (5, 5)
            return altar

    def test_negative_for_ladder_room(self):
        altar = self._make_altar()
        room = _make_room(has_ladder=True)
        self.assertLess(altar.score_room(_make_df(), room), 0)

    def test_negative_when_no_thing_coords(self):
        altar = self._make_altar()
        altar._thing_coords = lambda df, room: None
        room = _make_room(has_ladder=False)
        self.assertLess(altar.score_room(_make_df(), room), 0)

    def test_prefers_dungeon_tile_style(self):
        altar = self._make_altar()
        room_d = _make_room(tile_style="dungeon", has_ladder=False)
        room_c = _make_room(tile_style="cavern", has_ladder=False)
        df = _make_df()
        self.assertGreater(
            altar.score_room(df, room_d), altar.score_room(df, room_c)
        )

    def test_prefers_enclosed_rooms(self):
        altar = self._make_altar()
        room_enc = _make_room(enclosed=True, has_ladder=False)
        room_open = _make_room(enclosed=False, has_ladder=False)
        df = _make_df()
        self.assertGreater(
            altar.score_room(df, room_enc), altar.score_room(df, room_open)
        )

    def test_kryxix_prefers_dark(self):
        altar = self._make_altar("Kryxix")
        room_dark = _make_room(
            light_level="dark", has_ladder=False, total_space=9
        )
        room_bright = _make_room(
            light_level="bright", has_ladder=False, total_space=9
        )
        df = _make_df()
        score_dark = altar.score_room(df, room_dark)
        score_bright = altar.score_room(df, room_bright)
        self.assertGreater(score_dark, score_bright)

    def test_kryxix_zero_for_bright_room(self):
        altar = self._make_altar("Kryxix")
        room = _make_room(
            light_level="bright", has_ladder=False, total_space=9
        )
        self.assertEqual(altar.score_room(_make_df(), room), 0.0)

    def test_prefers_smaller_rooms(self):
        altar = self._make_altar()
        room_small = _make_room(total_space=9, has_ladder=False)
        room_big = _make_room(total_space=36, has_ladder=False)
        df = _make_df()
        self.assertGreater(
            altar.score_room(df, room_small), altar.score_room(df, room_big)
        )


class TestAltarThingCoords(unittest.TestCase):
    """Test Altar._thing_coords() placement logic."""

    @patch("random.random", return_value=0.0)
    @patch("random.choice")
    def test_returns_none_when_all_blocking(self, mock_choice, _):
        lib = deity_library()
        mock_choice.return_value = lib["Kryxix"].requests[0]
        altar = Altar("Kryxix")

        room = MagicMock()
        room.tile_coords.return_value = [(5, 5)]
        df = _make_df()
        blocking_tile = MagicMock()
        blocking_tile.is_move_blocking.return_value = True
        df.get_tile.return_value = blocking_tile
        df.neighbor_tiles.return_value = []

        result = altar._thing_coords(df, room)
        self.assertIsNone(result)

    @patch("random.random", return_value=0.0)
    @patch("random.choice")
    def test_returns_tuple_for_valid_placement(self, mock_choice, _):
        lib = deity_library()
        mock_choice.return_value = lib["Kryxix"].requests[0]
        altar = Altar("Kryxix")

        room = MagicMock()
        room.tile_coords.return_value = [(5, 5)]
        df = _make_df()
        floor_tile = RoomFloorTile(5, 5)
        df.get_tile.return_value = floor_tile
        # No walls or corridors nearby → score = 1.0
        df.neighbor_tiles.return_value = [RoomFloorTile(6, 5)]

        result = altar._thing_coords(df, room)
        self.assertIsNotNone(result)
        self.assertEqual(result, (5, 5))

    @patch("random.random", return_value=0.0)
    @patch("random.choice")
    def test_avoids_corridor_adjacent(self, mock_choice, _):
        lib = deity_library()
        mock_choice.return_value = lib["Kryxix"].requests[0]
        altar = Altar("Kryxix")

        room = MagicMock()
        room.tile_coords.return_value = [(5, 5)]
        df = _make_df()
        floor_tile = RoomFloorTile(5, 5)
        df.get_tile.return_value = floor_tile
        # Corridor nearby → score *= 0.0
        df.neighbor_tiles.return_value = [CorridorFloorTile(4, 5)]

        result = altar._thing_coords(df, room)
        self.assertIsNone(result)


class TestAltarPostProcess(unittest.TestCase):
    """Test Altar.post_process() door strength upgrade."""

    def _make_altar(self, deity_name="Ssarthaxx"):
        with patch("random.random", return_value=0.0), patch(
            "random.choice"
        ) as mock_choice:
            lib = deity_library()
            mock_choice.return_value = lib[deity_name].requests[0]
            return Altar(deity_name)

    def test_applies_minimum_door_strength(self):
        altar = self._make_altar("Ssarthaxx")
        altar.roomix = 0
        door = MagicMock()
        room = _make_room(doorixs=[0])
        df = _make_df(rooms=[room])
        df.doors = [door]
        altar.post_process(df)
        door.apply_minimum_door_strength.assert_called_once_with("Stone Door")

    def test_no_minimum_door_strength_skips(self):
        altar = self._make_altar("Kryxix")
        altar.roomix = 0
        door = MagicMock()
        room = _make_room(doorixs=[0])
        df = _make_df(rooms=[room])
        df.doors = [door]
        altar.post_process(df)
        door.apply_minimum_door_strength.assert_not_called()


class TestAltarAsciiChars(unittest.TestCase):
    """Test Altar.ascii_chars()."""

    @patch("random.random", return_value=0.0)
    @patch("random.choice")
    def test_returns_single_char(self, mock_choice, _):
        lib = deity_library()
        mock_choice.return_value = lib["Kryxix"].requests[0]
        altar = Altar("Kryxix")
        altar.roomix = 0
        room = MagicMock()
        df = _make_df(rooms=[room])
        altar._thing_coords = lambda df, room: (7, 8)
        chars = altar.ascii_chars(df)
        self.assertEqual(len(chars), 1)
        self.assertEqual(chars[0][0], 7)
        self.assertEqual(chars[0][1], 8)
        self.assertIn("&", chars[0][2])
        self.assertIn(lib["Kryxix"].ascii_color, chars[0][2])


if __name__ == "__main__":
    unittest.main()
