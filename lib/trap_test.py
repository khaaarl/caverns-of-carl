"""Unit tests for lib/trap.py"""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from lib.trap import (
    _AREA_TRAP_TRIGGERS,
    _CORRIDOR_TRAP_TRIGGERS,
    _DAMAGE_TYPE_DEFAULT_DICE,
    _DISEASES,
    _ENCLOSED_DOORS_TRAP_EFFECTS,
    _ENEMY_CORRIDOR_TRAP_EFFECTS,
    _LONG_DEBUFF_TRAP_EFFECTS,
    _MEDIUM_DEBUFF_TRAP_EFFECTS,
    _MISC_CORRIDOR_TRAP_EFFECTS,
    _MISC_ROOM_OR_CORRIDOR_TRAP_EFFECTS,
    _MISC_TRAP_EFFECTS,
    _ONE_OFF_DAMAGE_TRAP_EFFECTS,
    _SHORT_DEBUFF_TRAP_EFFECTS,
    _SLOW_DAMAGE_TRAP_EFFECTS,
    ChestTrap,
    CorridorTrap,
    DoorTrap,
    RoomTrap,
    Trap,
)


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

from lib.config import DungeonConfig


def _make_config(level=5):
    """Create a DungeonConfig with given level for trap testing."""
    config = DungeonConfig()
    config.target_character_level = level
    return config


# --- Trap base class ---


class TestTrapInit(unittest.TestCase):
    """Test Trap.__init__ and basic attributes."""

    @patch("lib.trap.random_dc", return_value=14)
    def test_stores_config(self, _mock_dc):
        config = _make_config(5)
        trap = Trap(config)
        self.assertIs(trap.config, config)

    @patch("lib.trap.random_dc", return_value=14)
    def test_stores_level_from_config(self, _mock_dc):
        config = _make_config(8)
        trap = Trap(config)
        self.assertEqual(trap.level, 8)

    @patch("lib.trap.random_dc", side_effect=[12, 15])
    def test_generates_notice_and_disarm_dc(self, _mock_dc):
        trap = Trap(_make_config())
        self.assertEqual(trap.notice_dc, 12)
        self.assertEqual(trap.disarm_dc, 15)

    @patch("lib.trap.random_dc", return_value=14)
    def test_default_trigger_and_effect_empty(self, _mock_dc):
        trap = Trap(_make_config())
        self.assertEqual(trap.trigger, "")
        self.assertEqual(trap.effect, "")

    @patch("lib.trap.random_dc", return_value=14)
    def test_default_corridorix_and_roomix_none(self, _mock_dc):
        trap = Trap(_make_config())
        self.assertIsNone(trap.corridorix)
        self.assertIsNone(trap.roomIx)


class TestTrapDescription(unittest.TestCase):
    """Test Trap.description() output format."""

    @patch("lib.trap.random_dc", side_effect=[10, 13])
    def test_description_contains_dcs(self, _mock_dc):
        trap = Trap(_make_config())
        trap.trigger = "Tripwire"
        trap.effect = "Boom"
        desc = trap.description()
        self.assertIn("find DC:10", desc)
        self.assertIn("disarm DC:13", desc)

    @patch("lib.trap.random_dc", return_value=14)
    def test_description_contains_trigger_and_effect(self, _mock_dc):
        trap = Trap(_make_config())
        trap.trigger = "Pressure plate"
        trap.effect = "Spikes"
        desc = trap.description()
        self.assertIn("Trigger: Pressure plate", desc)
        self.assertIn("Spikes", desc)


# --- eval_trap_expr ---


class TestEvalTrapExpr(unittest.TestCase):
    """Test the template token expansion in eval_trap_expr."""

    def setUp(self):
        with patch("lib.trap.random_dc", return_value=14):
            self.trap = Trap(_make_config(5))

    def test_plain_text_unchanged(self):
        self.assertEqual(
            self.trap.eval_trap_expr("Hello world"), "Hello world"
        )

    @patch("lib.trap.random_dc", return_value=15)
    def test_dc_token(self, _mock_dc):
        result = self.trap.eval_trap_expr("Dex {DC} for half")
        self.assertIn("DC:15", result)

    @patch("lib.trap.random_dc", return_value=15)
    def test_dc_with_modifier(self, _mock_dc):
        result = self.trap.eval_trap_expr("Wis {DC-2}")
        self.assertIn("DC:13", result)

    def test_ab_token_positive(self):
        self.trap.random_hit_bonus = lambda: 7
        result = self.trap.eval_trap_expr("{AB} to hit")
        self.assertIn("+7", result)

    def test_ab_token_negative(self):
        self.trap.random_hit_bonus = lambda: -1
        result = self.trap.eval_trap_expr("{AB} to hit")
        self.assertIn("-1", result)

    @patch("lib.trap.Trap.random_area", return_value="15' radius")
    def test_area_token(self, _mock_area):
        result = self.trap.eval_trap_expr("Explosion, {AREA}")
        self.assertIn("15' radius", result)

    @patch("random.choice", return_value="Blinding Sickness (PHB 227)")
    def test_disease_token(self, _mock_choice):
        result = self.trap.eval_trap_expr("infected with {DISEASE}")
        self.assertIn("Blinding Sickness", result)

    def test_dam_token_produces_damage_string(self):
        self.trap.random_avg_damage = lambda slow=False: 10.0
        result = self.trap.eval_trap_expr("{DAM:fire}")
        self.assertIn("fire damage", result)

    def test_dam_slow_modifier(self):
        calls = []
        original = self.trap.random_avg_damage

        def tracking_avg(slow=False):
            calls.append(slow)
            return 8.0

        self.trap.random_avg_damage = tracking_avg
        self.trap.eval_trap_expr("{DAM:fire,slow}")
        self.assertTrue(calls[0], "slow=True should be passed")

    def test_multiple_dam_splits_damage(self):
        """Two {DAM} tokens should each get half the total average damage."""
        self.trap.random_avg_damage = lambda slow=False: 20.0
        result = self.trap.eval_trap_expr("{DAM:piercing} & {DAM:poison}")
        self.assertIn("piercing damage", result)
        self.assertIn("poison damage", result)

    @patch(
        "random.randrange",
        return_value=0,
    )
    def test_short_debuff_trap_effect_token(self, _mock_rr):
        """SHORT_DEBUFF_TRAP_EFFECT should expand to first debuff entry."""
        result = self.trap.eval_trap_expr("{SHORT_DEBUFF_TRAP_EFFECT}")
        # First entry is "Blindness spell..."
        self.assertIn("Blindness", result)

    @patch("random.randrange", return_value=0)
    def test_slow_damage_trap_effect_token(self, _mock_rr):
        """SLOW_DAMAGE_TRAP_EFFECT should expand to first slow entry."""
        result = self.trap.eval_trap_expr("{SLOW_DAMAGE_TRAP_EFFECT}")
        self.assertIn("Poison gas", result)


# --- random_area ---


class TestTrapRandomArea(unittest.TestCase):
    """Test Trap.random_area()."""

    @patch("random.randrange", return_value=2)
    @patch("lib.trap.random_dc", return_value=14)
    def test_area_is_multiple_of_5(self, _mock_dc, _mock_rr):
        trap = Trap(_make_config(5))
        area = trap.random_area()
        # level=5 → range(1, 5) → mock returns 2 → 10' radius
        self.assertEqual(area, "10' radius")

    @patch("random.randrange", return_value=1)
    @patch("lib.trap.random_dc", return_value=14)
    def test_area_min_is_5(self, _mock_dc, _mock_rr):
        trap = Trap(_make_config(1))
        area = trap.random_area()
        self.assertEqual(area, "5' radius")


# --- random_hit_bonus ---


class TestTrapRandomHitBonus(unittest.TestCase):
    """Test Trap.random_hit_bonus()."""

    @patch("random.random", return_value=0.5)
    @patch("lib.trap.random_dc", return_value=14)
    def test_mid_roll_level_5(self, _mock_dc, _mock_rand):
        trap = Trap(_make_config(5))
        bonus = trap.random_hit_bonus()
        # mid = 5*0.65 + 2.5 = 5.75, plusminus = 2 + 0.5 = 2.5
        # b = 5.75 + 0.5*5.0 - 2.5 = 5.75
        self.assertEqual(bonus, 6)

    @patch("random.random", return_value=0.0)
    @patch("lib.trap.random_dc", return_value=14)
    def test_low_roll(self, _mock_dc, _mock_rand):
        trap = Trap(_make_config(5))
        bonus = trap.random_hit_bonus()
        # b = 5.75 + 0*5 - 2.5 = 3.25 → 3
        self.assertEqual(bonus, 3)

    @patch("random.random", return_value=1.0)
    @patch("lib.trap.random_dc", return_value=14)
    def test_high_roll(self, _mock_dc, _mock_rand):
        trap = Trap(_make_config(5))
        bonus = trap.random_hit_bonus()
        # b = 5.75 + 1.0*5 - 2.5 = 8.25 → 8
        self.assertEqual(bonus, 8)


# --- random_avg_damage ---


class TestTrapRandomAvgDamage(unittest.TestCase):
    """Test Trap.random_avg_damage()."""

    @patch("random.randrange", return_value=20)
    @patch("lib.trap.random_dc", return_value=14)
    def test_normal_damage(self, _mock_dc, _mock_rr):
        config = _make_config(5)
        config.trap_damage_low_multiplier = 3
        config.trap_damage_high_multiplier = 5
        trap = Trap(config)
        # lo=15, hi=25, randrange returns 20
        dam = trap.random_avg_damage()
        self.assertEqual(dam, 20)

    @patch("random.randrange", return_value=20)
    @patch("lib.trap.random_dc", return_value=14)
    def test_slow_damage_divides_by_4(self, _mock_dc, _mock_rr):
        config = _make_config(5)
        config.trap_damage_low_multiplier = 3
        config.trap_damage_high_multiplier = 5
        trap = Trap(config)
        dam = trap.random_avg_damage(slow=True)
        self.assertEqual(dam, 5.0)


# --- random_damage_dice_expr ---


class TestTrapRandomDamageDiceExpr(unittest.TestCase):
    """Test Trap.random_damage_dice_expr()."""

    @patch("lib.trap.random_dc", return_value=14)
    def test_very_low_returns_1(self, _mock_dc):
        trap = Trap(_make_config())
        # target_avg <= 1, d doesn't matter
        self.assertEqual(trap.random_damage_dice_expr(6, target_avg=0.5), "1")

    @patch("lib.trap.random_dc", return_value=14)
    def test_low_returns_1d4(self, _mock_dc):
        trap = Trap(_make_config())
        # d=12: threshold is 12/2-1=5, target_avg=2 < 5, and 1 < 2 <= 3
        self.assertEqual(trap.random_damage_dice_expr(12, target_avg=2), "1d4")

    @patch("lib.trap.random_dc", return_value=14)
    def test_returns_1d6(self, _mock_dc):
        trap = Trap(_make_config())
        # d=12: threshold=5, target_avg=3.5 < 5, and 3 < 3.5 <= 4
        self.assertEqual(
            trap.random_damage_dice_expr(12, target_avg=3.5), "1d6"
        )

    @patch("lib.trap.random_dc", return_value=14)
    def test_returns_1d8(self, _mock_dc):
        trap = Trap(_make_config())
        # d=12: threshold=5, target_avg=4.5 < 5, and 4 < 4.5 <= 5
        self.assertEqual(
            trap.random_damage_dice_expr(12, target_avg=4.5), "1d8"
        )

    @patch("lib.trap.random_dc", return_value=14)
    def test_returns_1d10(self, _mock_dc):
        trap = Trap(_make_config())
        # d=24: threshold=24/2-1=11, target_avg=5.5 < 11, and 5 < 5.5 <= 6
        self.assertEqual(
            trap.random_damage_dice_expr(24, target_avg=5.5), "1d10"
        )

    @patch("lib.trap.random_dc", return_value=14)
    def test_returns_1d12(self, _mock_dc):
        trap = Trap(_make_config())
        # d=24: threshold=11, target_avg=6.5 < 11, and 6 < 6.5
        self.assertEqual(
            trap.random_damage_dice_expr(24, target_avg=6.5), "1d12"
        )

    @patch("lib.trap.random_dc", return_value=14)
    def test_normal_dice_expression(self, _mock_dc):
        trap = Trap(_make_config())
        # target_avg=14, d=6 → round(14 / 3.5) = 4 → "4d6"
        self.assertEqual(trap.random_damage_dice_expr(6, target_avg=14), "4d6")

    @patch("lib.trap.random_dc", return_value=14)
    def test_minimum_1_die(self, _mock_dc):
        trap = Trap(_make_config())
        # target_avg just above threshold but rounds to 0 dice → clamp to 1
        # d=6, target_avg=2 → below threshold (6/2-1=2), returns "1d4"
        # d=6, target_avg=3 → 3 >= 2, enters formula: round(3/3.5)=1 → "1d6"
        self.assertEqual(trap.random_damage_dice_expr(6, target_avg=3), "1d6")

    @patch("lib.trap.random_dc", return_value=14)
    def test_no_target_avg_uses_random(self, _mock_dc):
        trap = Trap(_make_config())
        trap.random_avg_damage = lambda: 21.0
        # d=6, avg=21 → round(21/3.5) = 6 → "6d6"
        result = trap.random_damage_dice_expr(6)
        self.assertEqual(result, "6d6")


# --- ChestTrap ---


class TestChestTrap(unittest.TestCase):
    """Test ChestTrap creation and description."""

    @patch("lib.trap.random_dc", return_value=14)
    def test_stores_coordinates(self, _mock_dc):
        trap = ChestTrap(_make_config(), 10, 20)
        self.assertEqual(trap.x, 10)
        self.assertEqual(trap.y, 20)

    @patch("lib.trap.random_dc", return_value=14)
    def test_description_starts_with_chest(self, _mock_dc):
        trap = ChestTrap(_make_config(), 0, 0)
        trap.trigger = "Opening"
        trap.effect = "Boom"
        self.assertTrue(trap.description().startswith("Chest Trap"))

    @patch("random.choice")
    @patch("lib.trap.random_dc", return_value=14)
    def test_create_sets_trigger(self, _mock_dc, mock_choice):
        mock_choice.return_value = (
            "Thunderous Alarm: alerts nearby rooms' enemies"
        )
        trap = ChestTrap.create(_make_config(), 5, 5)
        self.assertEqual(trap.trigger, "Opening or tampering")

    @patch("random.choice")
    @patch("lib.trap.random_dc", return_value=14)
    def test_create_effect_pool_includes_expected_lists(
        self, _mock_dc, mock_choice
    ):
        """ChestTrap.create draws from one-off, misc, medium debuff, long debuff."""
        mock_choice.return_value = (
            "Thunderous Alarm: alerts nearby rooms' enemies"
        )
        trap = ChestTrap.create(_make_config(), 5, 5)
        # Verify mock_choice was called with combined effect list
        called_effs = mock_choice.call_args[0][0]
        expected_len = (
            len(_ONE_OFF_DAMAGE_TRAP_EFFECTS)
            + len(_MISC_TRAP_EFFECTS)
            + len(_MEDIUM_DEBUFF_TRAP_EFFECTS)
            + len(_LONG_DEBUFF_TRAP_EFFECTS)
        )
        self.assertEqual(len(called_effs), expected_len)


# --- RoomTrap ---


class TestRoomTrap(unittest.TestCase):
    """Test RoomTrap creation and behavior."""

    @patch("lib.trap.random_dc", return_value=14)
    def test_stores_roomix(self, _mock_dc):
        trap = RoomTrap(_make_config(), 3)
        self.assertEqual(trap.roomix, 3)

    @patch("lib.trap.random_dc", return_value=14)
    def test_description_starts_with_room(self, _mock_dc):
        trap = RoomTrap(_make_config(), 0)
        trap.trigger = "Runes"
        trap.effect = "Fire"
        self.assertTrue(trap.description().startswith("Room Trap"))

    @patch("random.choice")
    @patch("lib.trap.random_dc", return_value=14)
    def test_create_trigger_from_area_triggers(self, _mock_dc, mock_choice):
        mock_choice.side_effect = [
            "Scattered pressure plates",  # trigger
            "Thunderous Alarm: alerts nearby rooms' enemies",  # effect
        ]
        room = MagicMock()
        room.ix = 2
        room.is_fully_enclosed_by_doors.return_value = False
        trap = RoomTrap.create(_make_config(), room)
        self.assertIn(trap.trigger, _AREA_TRAP_TRIGGERS)

    @patch("random.choice")
    @patch("lib.trap.random_dc", return_value=14)
    def test_create_enclosed_room_adds_enclosed_effects(
        self, _mock_dc, mock_choice
    ):
        mock_choice.return_value = (
            "Thunderous Alarm: alerts nearby rooms' enemies"
        )
        room = MagicMock()
        room.ix = 1
        room.is_fully_enclosed_by_doors.return_value = True
        RoomTrap.create(_make_config(), room)
        called_effs = mock_choice.call_args_list[-1][0][0]
        expected_len = (
            len(_ONE_OFF_DAMAGE_TRAP_EFFECTS)
            + len(_SLOW_DAMAGE_TRAP_EFFECTS)
            + len(_MISC_TRAP_EFFECTS)
            + len(_MISC_ROOM_OR_CORRIDOR_TRAP_EFFECTS)
            + len(_ENCLOSED_DOORS_TRAP_EFFECTS)
        )
        self.assertEqual(len(called_effs), expected_len)

    @patch("random.choice")
    @patch("lib.trap.random_dc", return_value=14)
    def test_create_not_enclosed_excludes_enclosed_effects(
        self, _mock_dc, mock_choice
    ):
        mock_choice.return_value = (
            "Thunderous Alarm: alerts nearby rooms' enemies"
        )
        room = MagicMock()
        room.ix = 1
        room.is_fully_enclosed_by_doors.return_value = False
        RoomTrap.create(_make_config(), room)
        called_effs = mock_choice.call_args_list[-1][0][0]
        expected_len = (
            len(_ONE_OFF_DAMAGE_TRAP_EFFECTS)
            + len(_SLOW_DAMAGE_TRAP_EFFECTS)
            + len(_MISC_TRAP_EFFECTS)
            + len(_MISC_ROOM_OR_CORRIDOR_TRAP_EFFECTS)
        )
        self.assertEqual(len(called_effs), expected_len)

    @patch("random.randrange")
    @patch("lib.trap.random_dc", return_value=14)
    def test_random_area_can_return_whole_room(self, _mock_dc, mock_rr):
        trap = RoomTrap(_make_config(), 0)
        mock_rr.return_value = 0  # 0 → "whole room"
        self.assertEqual(trap.random_area(), "whole room")

    @patch("random.randrange", side_effect=[1, 3])
    @patch("lib.trap.random_dc", return_value=14)
    def test_random_area_can_return_radius(self, _mock_dc, _mock_rr):
        trap = RoomTrap(_make_config(5), roomix=0)
        # first randrange(2) returns 1 (truthy) → calls super
        # super: 5 * randrange(1, 5) → 5 * 3 = 15
        self.assertEqual(trap.random_area(), "15' radius")


# --- CorridorTrap ---


class TestCorridorTrap(unittest.TestCase):
    """Test CorridorTrap creation and behavior."""

    @patch("lib.trap.random_dc", return_value=14)
    def test_stores_corridorix(self, _mock_dc):
        trap = CorridorTrap(_make_config(), 5)
        self.assertEqual(trap.corridorix, 5)

    @patch("lib.trap.random_dc", return_value=14)
    def test_description_starts_with_corridor(self, _mock_dc):
        trap = CorridorTrap(_make_config(), 0)
        trap.trigger = "Wire"
        trap.effect = "Boom"
        self.assertTrue(trap.description().startswith("Corridor Trap"))

    @patch("random.choice")
    @patch("lib.trap.random_dc", return_value=14)
    def test_create_trigger_from_combined_triggers(
        self, _mock_dc, mock_choice
    ):
        mock_choice.return_value = (
            "Thunderous Alarm: alerts nearby rooms' enemies"
        )
        corridor = MagicMock()
        corridor.ix = 1
        corridor.is_fully_enclosed_by_doors.return_value = False
        CorridorTrap.create(_make_config(), corridor)
        trigger_choices = mock_choice.call_args_list[0][0][0]
        self.assertEqual(
            len(trigger_choices),
            len(_AREA_TRAP_TRIGGERS) + len(_CORRIDOR_TRAP_TRIGGERS),
        )

    @patch("random.choice")
    @patch("lib.trap.random_dc", return_value=14)
    def test_create_enclosed_corridor_adds_enclosed_effects(
        self, _mock_dc, mock_choice
    ):
        mock_choice.return_value = (
            "Thunderous Alarm: alerts nearby rooms' enemies"
        )
        corridor = MagicMock()
        corridor.ix = 1
        corridor.is_fully_enclosed_by_doors.return_value = True
        CorridorTrap.create(_make_config(), corridor)
        effect_choices = mock_choice.call_args_list[-1][0][0]
        self.assertIn(_ENCLOSED_DOORS_TRAP_EFFECTS[0], effect_choices)

    @patch("random.choice")
    @patch("lib.trap.random_dc", return_value=14)
    def test_create_many_encounters_adds_enemy_effects(
        self, _mock_dc, mock_choice
    ):
        mock_choice.return_value = (
            "Thunderous Alarm: alerts nearby rooms' enemies"
        )
        corridor = MagicMock()
        corridor.ix = 1
        corridor.is_fully_enclosed_by_doors.return_value = False
        CorridorTrap.create(_make_config(), corridor, num_nearby_encounters=2)
        effect_choices = mock_choice.call_args_list[-1][0][0]
        self.assertIn(_ENEMY_CORRIDOR_TRAP_EFFECTS[0], effect_choices)

    @patch("random.choice")
    @patch("lib.trap.random_dc", return_value=14)
    def test_create_few_encounters_excludes_enemy_effects(
        self, _mock_dc, mock_choice
    ):
        mock_choice.return_value = (
            "Thunderous Alarm: alerts nearby rooms' enemies"
        )
        corridor = MagicMock()
        corridor.ix = 1
        corridor.is_fully_enclosed_by_doors.return_value = False
        CorridorTrap.create(_make_config(), corridor, num_nearby_encounters=1)
        effect_choices = mock_choice.call_args_list[-1][0][0]
        for eff in _ENEMY_CORRIDOR_TRAP_EFFECTS:
            self.assertNotIn(eff, effect_choices)

    @patch("random.randrange")
    @patch("lib.trap.random_dc", return_value=14)
    def test_random_area_can_return_whole_corridor(self, _mock_dc, mock_rr):
        trap = CorridorTrap(_make_config(), 0)
        mock_rr.return_value = 0
        self.assertEqual(trap.random_area(), "whole corridor")

    @patch("random.randrange", side_effect=[1, 2])
    @patch("lib.trap.random_dc", return_value=14)
    def test_random_area_can_return_radius(self, _mock_dc, _mock_rr):
        trap = CorridorTrap(_make_config(5), corridorix=0)
        self.assertEqual(trap.random_area(), "10' radius")


# --- DoorTrap ---


class TestDoorTrap(unittest.TestCase):
    """Test DoorTrap creation and description."""

    @patch("lib.trap.random_dc", return_value=14)
    def test_stores_attributes(self, _mock_dc):
        trap = DoorTrap(_make_config(), doorix=3, x=10, y=20)
        self.assertEqual(trap.doorix, 3)
        self.assertEqual(trap.x, 10)
        self.assertEqual(trap.y, 20)

    @patch("lib.trap.random_dc", return_value=14)
    def test_description_starts_with_door(self, _mock_dc):
        trap = DoorTrap(_make_config(), 0, 0, 0)
        trap.trigger = "Handle"
        trap.effect = "Zap"
        self.assertTrue(trap.description().startswith("Door Trap"))

    @patch("random.choice")
    @patch("lib.trap.random_dc", return_value=14)
    def test_create_sets_trigger(self, _mock_dc, mock_choice):
        mock_choice.return_value = (
            "Thunderous Alarm: alerts nearby rooms' enemies"
        )
        trap = DoorTrap.create(_make_config(), corridorix=1, x=5, y=5)
        self.assertEqual(trap.trigger, "Opening or tampering")

    @patch("random.choice")
    @patch("lib.trap.random_dc", return_value=14)
    def test_create_effect_pool(self, _mock_dc, mock_choice):
        mock_choice.return_value = (
            "Thunderous Alarm: alerts nearby rooms' enemies"
        )
        DoorTrap.create(_make_config(), corridorix=1, x=5, y=5)
        called_effs = mock_choice.call_args[0][0]
        expected_len = len(_ONE_OFF_DAMAGE_TRAP_EFFECTS) + len(
            _MISC_TRAP_EFFECTS
        )
        self.assertEqual(len(called_effs), expected_len)


# --- Data lists ---


class TestTrapDataLists(unittest.TestCase):
    """Test that trap data lists are non-empty and contain strings."""

    def test_area_trap_triggers_nonempty(self):
        self.assertGreater(len(_AREA_TRAP_TRIGGERS), 0)
        for t in _AREA_TRAP_TRIGGERS:
            self.assertIsInstance(t, str)

    def test_corridor_trap_triggers_nonempty(self):
        self.assertGreater(len(_CORRIDOR_TRAP_TRIGGERS), 0)

    def test_one_off_damage_effects_have_tokens(self):
        for eff in _ONE_OFF_DAMAGE_TRAP_EFFECTS:
            self.assertTrue(
                "{DAM" in eff or "{AB" in eff or "{DC" in eff,
                f"Expected token in: {eff}",
            )

    def test_slow_damage_effects_have_slow_token(self):
        for eff in _SLOW_DAMAGE_TRAP_EFFECTS:
            self.assertIn("slow", eff)

    def test_diseases_nonempty(self):
        self.assertGreater(len(_DISEASES), 0)

    def test_damage_type_defaults(self):
        self.assertEqual(_DAMAGE_TYPE_DEFAULT_DICE["acid"], 4)
        self.assertEqual(_DAMAGE_TYPE_DEFAULT_DICE["poison"], 8)
        self.assertEqual(_DAMAGE_TYPE_DEFAULT_DICE["cold"], 8)
        self.assertEqual(_DAMAGE_TYPE_DEFAULT_DICE["fire"], 6)  # default


if __name__ == "__main__":
    unittest.main()
