"""
Unit tests for lib/embellish.py and lib/embellish_settings.py

Tests cover settings persistence, scope/cost estimation, prompt building,
embellishment application, and the Anthropic provider (mocked).
"""

import http.client
import io
import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

from lib.dungeon import DungeonFloor
from lib.room import CavernousRoom, RectRoom


def mock_tkinter():
    """Mock tkinter for headless testing."""
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

from lib.config import DungeonConfig

# Now import the modules under test
from lib.embellish import (
    _FEW_SHOT_EXAMPLES,
    PROVIDER_MODELS,
    AnthropicProvider,
    EmbellishmentResult,
    EmbellishmentScope,
    _direction_from_point,
    _extract_api_error_message,
    _extract_biome_section,
    _format_monsters,
    _gather_biome_stats,
    _get_few_shot_examples,
    _inject_atmosphere,
    _parse_book_response,
    _system_prompt,
    apply_embellishments,
    build_atmosphere_prompt,
    build_book_prompt,
    build_corridor_prompt,
    build_room_prompt,
    build_trap_prompt,
    write_log_file,
)
from lib.embellish_settings import (
    _DEFAULTS,
    load_settings,
    save_settings,
    settings_dir,
    settings_path,
)

# -----------------------------------------------------------------------
# Settings tests
# -----------------------------------------------------------------------


class TestEmbellishSettings(unittest.TestCase):
    """Tests for embellish_settings.py functions."""

    @patch("lib.embellish_settings.platform.system", return_value="Windows")
    @patch.dict(os.environ, {"APPDATA": "C:\\Users\\Test\\AppData\\Roaming"})
    def test_settings_dir_windows(self, mock_sys):
        d = settings_dir()
        self.assertIn("CavernsOfCarl", d)
        self.assertIn("AppData", d)

    @patch("lib.embellish_settings.platform.system", return_value="Darwin")
    def test_settings_dir_macos(self, mock_sys):
        d = settings_dir()
        self.assertIn("Library", d)
        self.assertIn("Application Support", d)
        self.assertIn("CavernsOfCarl", d)

    @patch("lib.embellish_settings.platform.system", return_value="Linux")
    @patch.dict(os.environ, {"XDG_CONFIG_HOME": "/tmp/test_xdg"}, clear=False)
    def test_settings_dir_linux_xdg(self, mock_sys):
        d = settings_dir()
        self.assertEqual(d, "/tmp/test_xdg/caverns-of-carl")

    @patch("lib.embellish_settings.platform.system", return_value="Linux")
    @patch.dict(os.environ, {}, clear=True)
    @patch("os.path.expanduser", return_value="/home/testuser")
    def test_settings_dir_linux_default(self, mock_expand, mock_sys):
        d = settings_dir()
        self.assertIn(".config", d)
        self.assertIn("caverns-of-carl", d)

    def test_load_save_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "settings.json")
            with patch(
                "lib.embellish_settings.settings_path", return_value=path
            ):
                settings = {"provider": "Anthropic", "model": "test-model"}
                save_settings(settings)
                loaded = load_settings()
                self.assertEqual(loaded["provider"], "Anthropic")
                self.assertEqual(loaded["model"], "test-model")

    def test_load_defaults_when_no_file(self):
        with patch(
            "lib.embellish_settings.settings_path",
            return_value="/nonexistent/path/settings.json",
        ):
            loaded = load_settings()
            for key, val in _DEFAULTS.items():
                self.assertEqual(loaded[key], val)

    def test_load_handles_corrupted_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "settings.json")
            with open(path, "w") as f:
                f.write("not valid json{{{")
            with patch(
                "lib.embellish_settings.settings_path", return_value=path
            ):
                loaded = load_settings()
                self.assertEqual(loaded["provider"], "Anthropic")


# -----------------------------------------------------------------------
# Scope & estimation tests
# -----------------------------------------------------------------------


class TestEmbellishScope(unittest.TestCase):
    """Tests for EmbellishmentScope cost/time estimation."""

    def setUp(self):
        self.config = DungeonConfig()
        self.df = DungeonFloor(self.config)
        # Add some rooms
        room1 = RectRoom(10, 10, rw=3, rh=3)
        room2 = RectRoom(20, 20, rw=2, rh=2)
        self.df.add_room(room1)
        self.df.add_room(room2)

    def test_count_rooms(self):
        scope = EmbellishmentScope(
            rooms=True, corridors=False, traps=False, books=False
        )
        elements = scope.count_elements(self.df)
        self.assertEqual(elements["room"], 2)

    def test_count_no_scope(self):
        scope = EmbellishmentScope(
            rooms=False, corridors=False, traps=False, books=False
        )
        self.assertEqual(scope.count_api_calls(self.df), 0)

    def test_count_includes_atmosphere_call(self):
        scope = EmbellishmentScope(
            rooms=True, corridors=False, traps=False, books=False
        )
        elements = scope.count_elements(self.df)
        # API calls = element count + 1 for atmosphere brief
        self.assertEqual(scope.count_api_calls(self.df), elements["room"] + 1)

    def test_cost_estimate_positive(self):
        scope = EmbellishmentScope(rooms=True)
        cost = scope.estimate_cost_usd(self.df, "claude-sonnet-4-5-20250929")
        self.assertGreater(cost, 0)

    def test_time_estimate_positive(self):
        scope = EmbellishmentScope(rooms=True)
        time_s = scope.estimate_time_seconds(self.df)
        self.assertGreater(time_s, 0)

    def test_time_estimate_includes_atmosphere_overhead(self):
        scope = EmbellishmentScope(rooms=True)
        time_s = scope.estimate_time_seconds(self.df)
        # Should include 3s for atmosphere brief
        self.assertGreaterEqual(time_s, 3.0)

    def test_haiku_cheaper_than_sonnet(self):
        scope = EmbellishmentScope(rooms=True)
        sonnet_cost = scope.estimate_cost_usd(
            self.df, "claude-sonnet-4-5-20250929"
        )
        haiku_cost = scope.estimate_cost_usd(
            self.df, "claude-haiku-4-5-20251001"
        )
        self.assertLess(haiku_cost, sonnet_cost)


# -----------------------------------------------------------------------
# Prompt building tests
# -----------------------------------------------------------------------


class TestPromptBuilding(unittest.TestCase):
    """Tests for prompt builder functions."""

    def setUp(self):
        self.config = DungeonConfig()
        self.df = DungeonFloor(self.config)
        self.room = RectRoom(15, 15, rw=4, rh=3, biome_name="Biome 1")
        self.room.light_level = "dim"
        self.room.name_num = 1
        self.df.add_room(self.room)

    def test_room_prompt_contains_room_name(self):
        sys_p, usr_p = build_room_prompt(self.df, self.room, "Classic D&D")
        self.assertIn("Room 1", usr_p)

    def test_room_prompt_contains_dimensions_in_feet(self):
        sys_p, usr_p = build_room_prompt(self.df, self.room, "Classic D&D")
        # 9 tiles * 5 = 45 ft, 7 tiles * 5 = 35 ft
        self.assertIn("45 ft", usr_p)
        self.assertIn("35 ft", usr_p)

    def test_room_prompt_contains_light_level(self):
        sys_p, usr_p = build_room_prompt(self.df, self.room, "Classic D&D")
        self.assertIn("dim", usr_p)

    def test_room_prompt_tone_in_system(self):
        sys_p, usr_p = build_room_prompt(self.df, self.room, "Grimdark")
        self.assertIn("bleak", sys_p)

    def test_corridor_prompt_contains_name(self):
        from lib.corridors import Corridor

        room2 = RectRoom(25, 15, rw=2, rh=2)
        self.df.add_room(room2)
        corridor = Corridor(0, 1, 19, 15, 23, 15, True, biome_name="Biome 1")
        corridor.name = "A"
        self.df.add_corridor(corridor)
        sys_p, usr_p = build_corridor_prompt(self.df, corridor, "Classic D&D")
        self.assertIn("A", usr_p)

    def test_trap_prompt_contains_trigger(self):
        from lib.trap import Trap

        trap = Trap(self.config)
        trap.trigger = "Pressure plate"
        trap.effect = "Poison darts"
        sys_p, usr_p = build_trap_prompt(self.df, trap, "Classic D&D")
        self.assertIn("Pressure plate", usr_p)
        self.assertIn("PASSIVE", sys_p)
        self.assertIn("PERCEPTION", sys_p)
        self.assertIn("INVESTIGATION", sys_p)

    def test_room_prompt_no_entry_instruction(self):
        sys_p, usr_p = build_room_prompt(self.df, self.room, "Classic D&D")
        self.assertIn("Do not describe the party entering", usr_p)

    def test_room_prompt_with_trap_has_trap_detected_section(self):
        from lib.trap import Trap

        trap = Trap(self.config)
        trap.trigger = "Pressure plate"
        trap.effect = "Poison darts"
        self.df.add_trap(trap)
        self.room.trapixs.add(0)
        sys_p, usr_p = build_room_prompt(self.df, self.room, "Classic D&D")
        self.assertIn("TRAP DETECTED:", sys_p)
        self.assertIn("must NOT mention the trap", sys_p)
        self.assertIn("Pressure plate", usr_p)

    def test_room_prompt_exits_with_corridor(self):
        from lib.corridors import Corridor

        room2 = RectRoom(25, 15, rw=2, rh=2)
        self.df.add_room(room2)
        corridor = Corridor(0, 1, 19, 15, 23, 15, True, biome_name="Biome 1")
        self.df.add_corridor(corridor)
        sys_p, usr_p = build_room_prompt(self.df, self.room, "Classic D&D")
        self.assertIn("Exits:", usr_p)
        self.assertIn("east", usr_p)

    def test_room_prompt_includes_chest(self):
        from lib.tile import ChestTile

        tile = ChestTile(0, contents="Gold coins")
        self.df.tiles[14][14] = tile
        sys_p, usr_p = build_room_prompt(self.df, self.room, "Classic D&D")
        self.assertIn("treasure chest", usr_p)

    def test_room_prompt_includes_bookshelf(self):
        from lib.tile import BookshelfTile

        tile = BookshelfTile(0, contents="Book: Ancient Tome")
        self.df.tiles[14][14] = tile
        sys_p, usr_p = build_room_prompt(self.df, self.room, "Classic D&D")
        self.assertIn("bookshelf", usr_p)

    def test_direction_from_point_east_wall(self):
        room = RectRoom(10, 10, rw=3, rh=3)
        # Point at east wall (x=13, y=10)
        self.assertEqual(_direction_from_point(room, 13, 10), "east")

    def test_direction_from_point_north_wall(self):
        room = RectRoom(10, 10, rw=3, rh=3)
        # Point at north wall (x=10, y=13)
        self.assertEqual(_direction_from_point(room, 10, 13), "north")

    def test_direction_from_point_south_wall(self):
        room = RectRoom(10, 10, rw=3, rh=3)
        # Point at south wall (x=10, y=7)
        self.assertEqual(_direction_from_point(room, 10, 7), "south")

    def test_direction_from_point_nonsquare_room(self):
        # Wide room (rw=5, rh=2): point at x+4,y+2 should be north
        # not east, because y+2 is at the north wall
        room = RectRoom(10, 10, rw=5, rh=2)
        self.assertEqual(_direction_from_point(room, 14, 12), "north")

    def test_format_monsters_consolidates_duplicates(self):
        m1 = MagicMock()
        m1.name = "Skeleton"
        m2 = MagicMock()
        m2.name = "Skeleton"
        m3 = MagicMock()
        m3.name = "Ogre"
        result = _format_monsters([m1, m2, m3])
        self.assertIn("2 Skeletons", result)
        self.assertIn("Ogre", result)

    def test_format_monsters_single(self):
        m1 = MagicMock()
        m1.name = "Goblin"
        result = _format_monsters([m1])
        self.assertEqual(result, "Goblin")

    def test_room_prompt_secret_door_handling(self):
        from lib.corridors import Corridor, Door

        room2 = RectRoom(25, 15, rw=2, rh=2)
        self.df.add_room(room2)
        corridor = Corridor(0, 1, 15, 15, 23, 15, True)
        self.df.add_corridor(corridor)
        door = Door(
            "Stone Door",
            corridor,
            19,
            15,
            roomixs=[0],
            is_secret=True,
            detection_dc=15,
        )
        self.df.add_door(door)
        corridor.doorixs.add(door.ix)
        self.room.doorixs.add(door.ix)
        sys_p, usr_p = build_room_prompt(self.df, self.room, "Classic D&D")
        self.assertIn("SECRET DOOR:", sys_p)
        self.assertIn("Do NOT mention", sys_p)
        self.assertIn("Secret exits:", usr_p)
        self.assertNotIn("Exits:", usr_p)

    def test_corridor_prompt_dimensions_in_feet(self):
        from lib.corridors import Corridor

        room2 = RectRoom(25, 15, rw=2, rh=2)
        self.df.add_room(room2)
        corridor = Corridor(0, 1, 19, 15, 23, 15, True, biome_name="Biome 1")
        corridor.name = "A"
        self.df.add_corridor(corridor)
        sys_p, usr_p = build_corridor_prompt(self.df, corridor, "Classic D&D")
        self.assertIn("ft", usr_p)
        self.assertNotIn("tiles", usr_p)

    def test_book_prompt_has_structured_format(self):
        sys_p, usr_p = build_book_prompt(self.df, "Classic D&D")
        self.assertIn("TITLE", sys_p)
        self.assertIn("AUTHOR", sys_p)
        self.assertIn("SYNOPSIS", sys_p)


# -----------------------------------------------------------------------
# Apply embellishments tests
# -----------------------------------------------------------------------


class TestApplyEmbellishments(unittest.TestCase):
    """Tests for apply_embellishments()."""

    def setUp(self):
        self.config = DungeonConfig()
        self.df = DungeonFloor(self.config)
        self.room = RectRoom(15, 15, rw=3, rh=3)
        self.room.name_num = 1
        self.df.add_room(self.room)

    def test_apply_room_flavor(self):
        results = [
            EmbellishmentResult(
                "room",
                0,
                "Room 1",
                "The air crackles with energy.",
                "sys",
                "usr",
            )
        ]
        apply_embellishments(self.df, results)
        self.assertEqual(
            self.df.rooms[0].flavor_text, "The air crackles with energy."
        )

    def test_flavor_text_in_room_description(self):
        self.room.flavor_text = "Ancient runes glow faintly on the walls."
        doc = self.room.description(self.df)
        body_text = doc.flat_body().unstyled()
        self.assertIn("Ancient runes glow faintly", body_text)

    def test_apply_trap_flavor(self):
        from lib.trap import Trap

        trap = Trap(self.config)
        trap.trigger = "Pressure plate"
        trap.effect = "Darts"
        self.df.add_trap(trap)
        results = [
            EmbellishmentResult(
                "trap",
                0,
                "Trap 1",
                "PASSIVE: Something feels off.\n"
                "PERCEPTION: You spot thin wires.\n"
                "INVESTIGATION: A pressure plate mechanism.",
                "sys",
                "usr",
            )
        ]
        apply_embellishments(self.df, results)
        self.assertIn("PASSIVE", self.df.traps[0].flavor_text)

    def test_apply_corridor_flavor(self):
        from lib.corridors import Corridor

        room2 = RectRoom(25, 15, rw=2, rh=2)
        self.df.add_room(room2)
        corridor = Corridor(0, 1, 19, 15, 23, 15, True)
        self.df.add_corridor(corridor)
        results = [
            EmbellishmentResult(
                "corridor",
                0,
                "Corridor A",
                "The passage narrows ahead.",
                "sys",
                "usr",
            )
        ]
        apply_embellishments(self.df, results)
        self.assertEqual(
            self.df.corridors[0].flavor_text, "The passage narrows ahead."
        )

    def test_apply_skips_errored_results(self):
        """Results with flavor_text=None (errors) should be skipped."""
        results = [
            EmbellishmentResult(
                "room",
                0,
                "Room 1",
                None,
                "sys",
                "usr",
                error="API error",
            )
        ]
        self.df.rooms[0].flavor_text = None
        apply_embellishments(self.df, results)
        self.assertIsNone(self.df.rooms[0].flavor_text)


# -----------------------------------------------------------------------
# Anthropic provider tests (mocked)
# -----------------------------------------------------------------------


class TestAnthropicProvider(unittest.TestCase):
    """Tests for AnthropicProvider with mocked HTTP calls."""

    def test_request_body_construction(self):
        provider = AnthropicProvider(
            api_key="test-key", model="claude-sonnet-4-5-20250929"
        )
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps(
                {"content": [{"type": "text", "text": "Generated text."}]}
            ).encode("utf-8")
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            result = provider.generate("System prompt", "User prompt")

            # Verify the request was made
            call_args = mock_urlopen.call_args
            req = call_args[0][0]
            self.assertEqual(req.get_header("X-api-key"), "test-key")
            self.assertEqual(req.get_header("Anthropic-version"), "2023-06-01")
            body = json.loads(req.data)
            self.assertEqual(body["model"], "claude-sonnet-4-5-20250929")
            self.assertEqual(body["system"], "System prompt")
            self.assertEqual(body["messages"][0]["content"], "User prompt")

    def test_response_parsing(self):
        provider = AnthropicProvider(api_key="test-key")
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps(
                {
                    "content": [
                        {
                            "type": "text",
                            "text": "The room smells of sulfur.",
                        }
                    ]
                }
            ).encode("utf-8")
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            result = provider.generate("sys", "usr")
            self.assertEqual(result, "The room smells of sulfur.")

    def test_error_handling_with_json_message(self):
        import urllib.error

        provider = AnthropicProvider(api_key="bad-key")
        error_json = json.dumps(
            {
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": "Your credit balance is too low.",
                },
            }
        ).encode("utf-8")
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                url="https://api.anthropic.com",
                code=400,
                msg="Bad Request",
                hdrs={},
                fp=io.BytesIO(error_json),
            )
            with self.assertRaises(RuntimeError) as ctx:
                provider.generate("sys", "usr")
            # Should get the clean message, not raw JSON
            self.assertIn("credit balance", str(ctx.exception))
            self.assertNotIn('"type"', str(ctx.exception))

    def test_error_handling_without_json(self):
        import urllib.error

        provider = AnthropicProvider(api_key="bad-key")
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                url="https://api.anthropic.com",
                code=401,
                msg="Unauthorized",
                hdrs={},
                fp=io.BytesIO(b"not json"),
            )
            with self.assertRaises(RuntimeError) as ctx:
                provider.generate("sys", "usr")
            self.assertIn("Invalid API key", str(ctx.exception))


# -----------------------------------------------------------------------
# API error message extraction tests
# -----------------------------------------------------------------------


class TestExtractApiErrorMessage(unittest.TestCase):
    """Tests for _extract_api_error_message helper."""

    def test_parses_anthropic_error_json(self):
        body = json.dumps(
            {
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": "Your credit balance is too low.",
                },
            }
        )
        msg = _extract_api_error_message(400, body)
        self.assertEqual(msg, "Your credit balance is too low.")

    def test_fallback_for_401(self):
        msg = _extract_api_error_message(401, "not json")
        self.assertIn("Invalid API key", msg)

    def test_fallback_for_429(self):
        msg = _extract_api_error_message(429, "{}")
        self.assertIn("Rate limited", msg)

    def test_fallback_for_unknown_code(self):
        msg = _extract_api_error_message(418, "teapot")
        self.assertIn("418", msg)


# -----------------------------------------------------------------------
# Book response parsing tests
# -----------------------------------------------------------------------


class TestParseBookResponse(unittest.TestCase):
    """Tests for _parse_book_response helper."""

    def test_parses_structured_response(self):
        text = (
            "TITLE: The Arcane Codex\n"
            "AUTHOR: Elminster\n"
            "DESCRIPTION: A leather-bound tome.\n"
            "SYNOPSIS: Ancient spells of power.\n"
            "EXCERPT: The stars align when magic flows."
        )
        result = _parse_book_response(text)
        self.assertEqual(result["TITLE"], "The Arcane Codex")
        self.assertEqual(result["AUTHOR"], "Elminster")
        self.assertIn("leather-bound", result["DESCRIPTION"])

    def test_returns_none_for_garbage(self):
        result = _parse_book_response("Just some random text.")
        self.assertIsNone(result)

    def test_partial_response(self):
        text = "TITLE: Half a Book\nAUTHOR: Nobody"
        result = _parse_book_response(text)
        self.assertEqual(result["TITLE"], "Half a Book")
        self.assertEqual(result["AUTHOR"], "Nobody")
        self.assertNotIn("SYNOPSIS", result)


# -----------------------------------------------------------------------
# Trap description with flavor text test
# -----------------------------------------------------------------------


class TestTrapDescription(unittest.TestCase):
    """Tests that Trap.description() includes flavor_text when set."""

    def test_trap_description_without_flavor(self):
        from lib.trap import Trap

        config = DungeonConfig()
        trap = Trap(config)
        trap.trigger = "Tripwire"
        trap.effect = "Arrows fly"
        desc = trap.description()
        self.assertIn("Trap (find DC:", desc)
        self.assertIn("Tripwire", desc)

    def test_trap_description_with_flavor(self):
        from lib.trap import Trap

        config = DungeonConfig()
        trap = Trap(config)
        trap.trigger = "Tripwire"
        trap.effect = "Arrows fly"
        trap.flavor_text = "Something feels wrong here."
        desc = trap.description()
        self.assertTrue(desc.startswith("Something feels wrong here."))
        self.assertIn("Trap (find DC:", desc)


# -----------------------------------------------------------------------
# EmbellishmentResult field tests
# -----------------------------------------------------------------------


class TestEmbellishmentResultFields(unittest.TestCase):
    """Tests for EmbellishmentResult new fields."""

    def test_all_fields_stored(self):
        r = EmbellishmentResult(
            "room",
            0,
            "Room 1",
            "Flavor text.",
            "system prompt",
            "user prompt",
            error=None,
            elapsed_seconds=1.5,
        )
        self.assertEqual(r.element_type, "room")
        self.assertEqual(r.element_id, 0)
        self.assertEqual(r.element_name, "Room 1")
        self.assertEqual(r.flavor_text, "Flavor text.")
        self.assertEqual(r.system_prompt, "system prompt")
        self.assertEqual(r.user_prompt, "user prompt")
        self.assertIsNone(r.error)
        self.assertEqual(r.elapsed_seconds, 1.5)

    def test_error_result_has_none_flavor(self):
        r = EmbellishmentResult(
            "room",
            0,
            "Room 1",
            None,
            "sys",
            "usr",
            error="Connection failed",
        )
        self.assertIsNone(r.flavor_text)
        self.assertEqual(r.error, "Connection failed")

    def test_defaults(self):
        r = EmbellishmentResult("trap", 1, "Trap 1", "text", "sys", "usr")
        self.assertIsNone(r.error)
        self.assertEqual(r.elapsed_seconds, 0.0)


# -----------------------------------------------------------------------
# write_log_file tests
# -----------------------------------------------------------------------


class TestWriteLogFile(unittest.TestCase):
    """Tests for write_log_file()."""

    def _make_results(self):
        return [
            EmbellishmentResult(
                "room",
                0,
                "Room 1",
                "The air crackles.",
                "system prompt",
                "user prompt",
                elapsed_seconds=1.23,
            ),
            EmbellishmentResult(
                "corridor",
                1,
                "Corridor A",
                None,
                "sys",
                "usr",
                error="API error",
                elapsed_seconds=0.3,
            ),
        ]

    def test_roundtrip_valid_jsonl(self):
        results = self._make_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("lib.embellish.COC_ROOT_DIR", tmpdir):
                path = write_log_file(results)
                self.assertTrue(os.path.isfile(path))
                with open(path) as f:
                    lines = f.readlines()
                self.assertEqual(len(lines), 2)
                for line in lines:
                    obj = json.loads(line)
                    self.assertIn("element_type", obj)
                    self.assertIn("system_prompt", obj)
                    self.assertIn("response", obj)
                    self.assertIn("error", obj)
                    self.assertIn("elapsed_seconds", obj)

    def test_creates_directory(self):
        results = self._make_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("lib.embellish.COC_ROOT_DIR", tmpdir):
                path = write_log_file(results)
                log_dir = os.path.dirname(path)
                self.assertTrue(os.path.isdir(log_dir))
                self.assertIn("embellish_logs", log_dir)

    def test_error_entries_included(self):
        results = self._make_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("lib.embellish.COC_ROOT_DIR", tmpdir):
                path = write_log_file(results)
                with open(path) as f:
                    lines = f.readlines()
                error_entry = json.loads(lines[1])
                self.assertEqual(error_entry["error"], "API error")
                self.assertIsNone(error_entry["response"])
                ok_entry = json.loads(lines[0])
                self.assertIsNone(ok_entry["error"])
                self.assertEqual(ok_entry["response"], "The air crackles.")


# -----------------------------------------------------------------------
# Few-shot examples tests
# -----------------------------------------------------------------------


class TestFewShotExamples(unittest.TestCase):
    """Tests for few-shot example infrastructure."""

    def test_all_preset_tones_have_examples(self):
        for tone in ("Classic D&D", "Grimdark", "Whimsical", "Lovecraftian"):
            examples = _get_few_shot_examples(tone)
            self.assertEqual(len(examples), 2, f"Missing examples for {tone}")

    def test_each_example_has_user_and_assistant(self):
        for tone, examples in _FEW_SHOT_EXAMPLES.items():
            for i, ex in enumerate(examples):
                self.assertIn("user", ex, f"{tone} example {i} missing user")
                self.assertIn(
                    "assistant", ex, f"{tone} example {i} missing assistant"
                )
                self.assertTrue(
                    len(ex["user"]) > 20,
                    f"{tone} example {i} user too short",
                )
                self.assertTrue(
                    len(ex["assistant"]) > 20,
                    f"{tone} example {i} assistant too short",
                )

    def test_custom_tone_falls_back_to_classic(self):
        custom = _get_few_shot_examples("Custom spooky tone")
        classic = _get_few_shot_examples("Classic D&D")
        self.assertEqual(custom, classic)

    def test_system_prompt_includes_examples(self):
        prompt = _system_prompt("Grimdark")
        self.assertIn("--- Example 1 ---", prompt)
        self.assertIn("--- Example 2 ---", prompt)
        self.assertIn("User:", prompt)
        self.assertIn("Assistant:", prompt)

    def test_examples_have_room_and_corridor(self):
        for tone, examples in _FEW_SHOT_EXAMPLES.items():
            has_room = any("Room:" in ex["user"] for ex in examples)
            has_corridor = any("Corridor:" in ex["user"] for ex in examples)
            self.assertTrue(has_room, f"{tone} missing room example")
            self.assertTrue(has_corridor, f"{tone} missing corridor example")


# -----------------------------------------------------------------------
# Atmosphere brief tests
# -----------------------------------------------------------------------


class TestGatherBiomeStats(unittest.TestCase):
    """Tests for _gather_biome_stats()."""

    def setUp(self):
        self.config = DungeonConfig()
        self.df = DungeonFloor(self.config)

    def test_single_biome_stats(self):
        room = RectRoom(15, 15, rw=3, rh=3)
        room.light_level = "dim"
        self.df.add_room(room)
        stats = _gather_biome_stats(self.df)
        # None biome_name for rooms without biome
        self.assertIn(None, stats)
        self.assertEqual(stats[None]["room_count"], 1)
        self.assertEqual(stats[None]["room_types"]["rectangular"], 1)
        self.assertEqual(stats[None]["light_counts"]["dim"], 1)

    def test_cavernous_room_counted(self):
        room = CavernousRoom(15, 15, rw=4, rh=4)
        room.light_level = "dark"
        self.df.add_room(room)
        stats = _gather_biome_stats(self.df)
        self.assertEqual(stats[None]["room_types"]["cavernous"], 1)

    def test_multi_biome_stats(self):
        biome = self.config.add_biome("Frozen Depths")
        room1 = RectRoom(10, 10, rw=3, rh=3)
        room1.light_level = "bright"
        self.df.add_room(room1)
        room2 = RectRoom(25, 25, rw=3, rh=3, biome_name="Frozen Depths")
        room2.light_level = "dark"
        self.df.add_room(room2)
        stats = _gather_biome_stats(self.df)
        self.assertIn(None, stats)
        self.assertIn("Frozen Depths", stats)
        self.assertEqual(stats[None]["room_count"], 1)
        self.assertEqual(stats["Frozen Depths"]["room_count"], 1)

    def test_monsters_collected(self):
        room = RectRoom(15, 15, rw=3, rh=3)
        room.light_level = "bright"
        encounter = MagicMock()
        m1 = MagicMock()
        m1.name = "Skeleton"
        m2 = MagicMock()
        m2.name = "Zombie"
        encounter.monsters = [m1, m2]
        room.encounter = encounter
        self.df.add_room(room)
        stats = _gather_biome_stats(self.df)
        self.assertIn("Skeleton", stats[None]["monster_names"])
        self.assertIn("Zombie", stats[None]["monster_names"])

    def test_trivial_rooms_excluded(self):
        from lib.room import MazeJunction

        room = MazeJunction(15, 15, rw=1, rh=1)
        self.df.add_room(room)
        stats = _gather_biome_stats(self.df)
        # Maze junctions are trivial so shouldn't add their biome
        for s in stats.values():
            self.assertEqual(s["room_count"], 0)


class TestBuildAtmospherePrompt(unittest.TestCase):
    """Tests for build_atmosphere_prompt()."""

    def setUp(self):
        self.config = DungeonConfig()
        self.df = DungeonFloor(self.config)
        room = RectRoom(15, 15, rw=3, rh=3)
        room.light_level = "dim"
        self.df.add_room(room)

    def test_includes_dimensions_in_feet(self):
        sys_p, usr_p = build_atmosphere_prompt(self.df, "Classic D&D")
        self.assertIn("ft", usr_p)

    def test_includes_room_count(self):
        sys_p, usr_p = build_atmosphere_prompt(self.df, "Classic D&D")
        self.assertIn("Rooms: 1", usr_p)

    def test_includes_tone_description(self):
        sys_p, usr_p = build_atmosphere_prompt(self.df, "Grimdark")
        self.assertIn("bleak", sys_p)

    def test_multi_biome_mentions_regions(self):
        self.config.add_biome("Frozen Depths")
        room2 = RectRoom(25, 25, rw=3, rh=3, biome_name="Frozen Depths")
        room2.light_level = "dark"
        self.df.add_room(room2)
        sys_p, usr_p = build_atmosphere_prompt(self.df, "Classic D&D")
        self.assertIn("Frozen Depths", usr_p)
        self.assertIn("multiple distinct regions", sys_p)


class TestInjectAtmosphere(unittest.TestCase):
    """Tests for _inject_atmosphere() and _extract_biome_section()."""

    def test_prepends_when_brief_exists(self):
        result = _inject_atmosphere(
            "Write about this room.", "Dark and damp.", None
        )
        self.assertTrue(result.startswith("Dungeon atmosphere context:"))
        self.assertIn("Dark and damp.", result)
        self.assertIn("Write about this room.", result)

    def test_returns_original_when_none(self):
        result = _inject_atmosphere("Write about this room.", None, None)
        self.assertEqual(result, "Write about this room.")

    def test_extract_biome_section_with_marker(self):
        brief = (
            "[Dungeon]\nDark stone halls.\n\n"
            "[Cavern]\nDripping stalactites."
        )
        section = _extract_biome_section(brief, "Cavern")
        self.assertIn("Dripping stalactites", section)
        self.assertNotIn("Dark stone halls", section)

    def test_extract_biome_section_no_marker(self):
        brief = "Just a general description of the dungeon."
        section = _extract_biome_section(brief, "Missing Biome")
        self.assertEqual(section, brief)

    def test_extract_biome_section_none_biome(self):
        brief = "[Dungeon]\nDark halls.\n[Cavern]\nDripping water."
        section = _extract_biome_section(brief, None)
        self.assertEqual(section, brief)

    def test_inject_extracts_correct_biome(self):
        brief = (
            "[Frozen Depths]\nIce-covered walls.\n\n"
            "[Fire Pits]\nLava flows below."
        )
        result = _inject_atmosphere("Room prompt here.", brief, "Fire Pits")
        self.assertIn("Lava flows below", result)
        self.assertNotIn("Ice-covered walls", result)


if __name__ == "__main__":
    unittest.main()
