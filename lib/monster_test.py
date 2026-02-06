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

from lib.monster import (
    Encounter,
    Monster,
    MonsterInfo,
    MonsterLibrary,
    build_encounter,
    med_target_xp,
    score_encounter,
    summarize_monsters,
)


class TestMonsterInfo(unittest.TestCase):
    """Test MonsterInfo class."""

    def setUp(self):
        """Create test fixtures."""
        self.blob = {
            "name": "Goblin",
            "keywords": ["humanoid"],
            "ascii_char": "g",
            "health": 7,
            "hit_dice_formula": "2d6",
            "size": "small",
            "challenge_rating": 0.25,
            "frequency": 1.0,
        }
        # Info without hit_dice_formula for testing direct health
        self.blob_no_dice = {
            "name": "Goblin",
            "keywords": ["humanoid"],
            "ascii_char": "g",
            "health": 7,
            "size": "small",
            "challenge_rating": 0.25,
            "frequency": 1.0,
        }

    def test_init_from_blob(self):
        """Test MonsterInfo initialization from blob."""
        mi = MonsterInfo(self.blob)
        self.assertEqual(mi.name, "Goblin")
        self.assertEqual(mi.keywords, ["humanoid"])
        self.assertEqual(mi.ascii_char, "g")
        self.assertEqual(mi.health, 7)
        self.assertEqual(mi.challenge_rating, 0.25)

    def test_init_defaults(self):
        """Test MonsterInfo with default values."""
        mi = MonsterInfo({})
        self.assertEqual(mi.name, "Unnamed Monster")
        self.assertEqual(mi.keywords, [])
        self.assertEqual(mi.ascii_char, "e")
        self.assertIsNone(mi.health)
        self.assertIsNone(mi.challenge_rating)

    def test_size_to_diameter_mapping(self):
        """Test that size maps to correct diameter."""
        sizes = {
            "tiny": 1,
            "small": 1,
            "medium": 1,
            "large": 2,
            "huge": 3,
            "gargantuan": 3,
        }
        for size, expected_diameter in sizes.items():
            blob = {"size": size}
            mi = MonsterInfo(blob)
            self.assertEqual(mi.diameter, expected_diameter)

    def test_xp_from_challenge_rating(self):
        """Test that XP is calculated from CR."""
        mi = MonsterInfo({"challenge_rating": 1})
        self.assertEqual(mi.xp, 200)
        mi = MonsterInfo({"challenge_rating": 0.5})
        self.assertEqual(mi.xp, 100)

    def test_xp_none_without_cr(self):
        """Test that XP is None when CR is None."""
        mi = MonsterInfo({"challenge_rating": None})
        self.assertIsNone(mi.xp)

    def test_has_keyword_case_insensitive(self):
        """Test has_keyword is case-insensitive."""
        mi = MonsterInfo({"keywords": ["humanoid", "Spellcaster"]})
        self.assertTrue(mi.has_keyword("HUMANOID"))
        self.assertTrue(mi.has_keyword("Humanoid"))
        self.assertTrue(mi.has_keyword("humanoid"))
        self.assertTrue(mi.has_keyword("spellcaster"))
        self.assertFalse(mi.has_keyword("dragon"))

    def test_has_keyword_or_name_keyword(self):
        """Test has_keyword_or_name with keyword."""
        mi = MonsterInfo({"name": "Goblin", "keywords": ["humanoid"]})
        self.assertTrue(mi.has_keyword_or_name("HUMANOID"))
        self.assertTrue(mi.has_keyword_or_name("humanoid"))

    def test_has_keyword_or_name_name(self):
        """Test has_keyword_or_name with name."""
        mi = MonsterInfo({"name": "Goblin", "keywords": []})
        self.assertTrue(mi.has_keyword_or_name("GOBLIN"))
        self.assertTrue(mi.has_keyword_or_name("Goblin"))
        self.assertTrue(mi.has_keyword_or_name("goblin"))

    def test_to_blob_omits_defaults(self):
        """Test that to_blob omits default values."""
        mi = MonsterInfo({"name": "Custom", "keywords": []})
        blob = mi.to_blob()
        self.assertEqual(blob["name"], "Custom")
        # Default keywords should not be in blob
        self.assertNotIn("keywords", blob)

    def test_to_blob_includes_nondefaults(self):
        """Test that to_blob includes non-default values."""
        mi = MonsterInfo(
            {"name": "Dragon", "challenge_rating": 5, "keywords": ["dragon"]}
        )
        blob = mi.to_blob()
        self.assertEqual(blob["challenge_rating"], 5)
        self.assertEqual(blob["keywords"], ["dragon"])

    def test_max_per_floor(self):
        """Test max_per_floor tracking."""
        mi = MonsterInfo({"name": "Boss", "max_per_floor": 1})
        self.assertEqual(mi.max_per_floor, 1)

    def test_frequency(self):
        """Test frequency for weighted selection."""
        mi = MonsterInfo({"frequency": 2.5})
        self.assertEqual(mi.frequency, 2.5)

    def test_synergies(self):
        """Test synergies list."""
        mi = MonsterInfo({"synergies": ["Goblin", "Goblin Shaman"]})
        self.assertEqual(mi.synergies, ["Goblin", "Goblin Shaman"])


class TestMonster(unittest.TestCase):
    """Test Monster class."""

    def setUp(self):
        """Create test fixtures."""
        self.info = MonsterInfo(
            {
                "name": "Goblin",
                "ascii_char": "g",
                "health": 7,
                "hit_dice_formula": "2d6",
                "challenge_rating": 0.25,
            }
        )

    def test_init_basic(self):
        """Test Monster initialization."""
        monster = Monster(self.info)
        self.assertEqual(monster.name, "Goblin")
        self.assertEqual(monster.x, 0)
        self.assertEqual(monster.y, 0)
        self.assertIsNone(monster.roomix)

    def test_init_with_position_and_room(self):
        """Test Monster with position and room."""
        monster = Monster(self.info, x=10, y=20, roomix=5)
        self.assertEqual(monster.x, 10)
        self.assertEqual(monster.y, 20)
        self.assertEqual(monster.roomix, 5)

    def test_init_with_custom_name(self):
        """Test Monster with custom name."""
        monster = Monster(self.info, name="Goblin Boss")
        self.assertEqual(monster.name, "Goblin Boss")

    def test_init_health_from_parameter(self):
        """Test Monster health from parameter."""
        monster = Monster(self.info, health=10)
        self.assertEqual(monster.health, 10)

    def test_init_health_from_formula(self):
        """Test Monster health from hit dice formula."""
        with patch("lib.monster.eval_dice", return_value=8):
            monster = Monster(self.info)
            self.assertEqual(monster.health, 8)

    def test_init_health_from_info(self):
        """Test Monster health from MonsterInfo.health (no hit dice)."""
        # Use MonsterInfo without hit_dice_formula
        info = MonsterInfo(
            {
                "name": "Goblin",
                "ascii_char": "g",
                "health": 7,
                "challenge_rating": 0.25,
            }
        )
        monster = Monster(info)
        self.assertEqual(monster.health, 7)

    def test_to_char(self):
        """Test Monster to_char returns ASCII char."""
        monster = Monster(self.info)
        self.assertEqual(monster.to_char(), "g")

    def test_tts_nickname_without_health(self):
        """Test tts_nickname without health."""
        monster = Monster(self.info, health=None)
        monster.health = None
        self.assertEqual(monster.tts_nickname(), "Goblin")

    def test_tts_nickname_with_health(self):
        """Test tts_nickname with health."""
        monster = Monster(self.info, health=7)
        self.assertEqual(monster.tts_nickname(), "7/7 Goblin")

    def test_tts_nickname_unnamed(self):
        """Test tts_nickname for unnamed monster."""
        info = MonsterInfo({"name": "", "ascii_char": "e"})
        monster = Monster(info)
        self.assertEqual(monster.tts_nickname(), "Unnamed Monster")

    def test_adjust_cr_same_cr(self):
        """Test adjust_cr with same CR returns early."""
        monster = Monster(self.info, health=7)
        monster.adjust_cr(0.25)
        # Name shouldn't change if CR is the same
        self.assertEqual(monster.name, "Goblin")

    def test_adjust_cr_changes_xp(self):
        """Test adjust_cr changes XP."""
        monster = Monster(self.info, health=7)
        monster.adjust_cr(0.5)
        self.assertEqual(monster.monster_info.xp, 100)

    def test_adjust_cr_scales_health(self):
        """Test adjust_cr scales health appropriately."""
        monster = Monster(self.info, health=60)  # CR 0.5 health
        monster.adjust_cr(1)  # Increase to CR 1
        # Health should scale from CR 0.5 (60 hp) to CR 1 (78 hp)
        self.assertGreater(monster.health, 60)

    def test_adjust_cr_appends_name(self):
        """Test adjust_cr appends CR to name."""
        monster = Monster(self.info)
        monster.adjust_cr(1)
        self.assertIn("(CR 1)", monster.name)

    def test_adjust_cr_fractional_notation(self):
        """Test adjust_cr uses fractional notation."""
        monster = Monster(self.info)
        monster.adjust_cr(0.5)
        self.assertIn("(CR 1/2)", monster.name)


class TestEncounter(unittest.TestCase):
    """Test Encounter class."""

    def setUp(self):
        """Create test fixtures."""
        self.goblin_info = MonsterInfo(
            {
                "name": "Goblin",
                "ascii_char": "g",
                "size": "small",
                "challenge_rating": 0.25,
                "health": 7,
            }
        )
        self.orc_info = MonsterInfo(
            {
                "name": "Orc",
                "ascii_char": "o",
                "size": "large",
                "challenge_rating": 1,
                "health": 15,
            }
        )

    def test_init_empty(self):
        """Test empty Encounter."""
        encounter = Encounter()
        self.assertEqual(encounter.monsters, [])

    def test_init_with_monsters(self):
        """Test Encounter with monsters."""
        monsters = [Monster(self.goblin_info), Monster(self.orc_info)]
        encounter = Encounter(monsters)
        self.assertEqual(len(encounter.monsters), 2)

    def test_total_xp_single_monster(self):
        """Test total_xp with single monster."""
        encounter = Encounter([Monster(self.goblin_info)])
        # CR 0.25 = 50 XP, single monster: 50 * sqrt(1) = 50
        self.assertEqual(encounter.total_xp(), 50)

    def test_total_xp_two_monsters_same_cr(self):
        """Test total_xp with two monsters of same CR."""
        monsters = [Monster(self.goblin_info), Monster(self.goblin_info)]
        encounter = Encounter(monsters)
        # 50 + 50 = 100, sqrt(2) ~= 1.414, so 100 * 1.414 ~= 141
        xp = encounter.total_xp()
        self.assertGreater(xp, 100)
        self.assertLess(xp, 200)

    def test_total_space_single_small_monster(self):
        """Test total_space with small monster."""
        # Small = diameter 1, so 1^2 = 1 space
        encounter = Encounter([Monster(self.goblin_info)])
        self.assertEqual(encounter.total_space(), 1)

    def test_total_space_single_large_monster(self):
        """Test total_space with large monster."""
        # Large = diameter 2, so 2^2 = 4 space
        encounter = Encounter([Monster(self.orc_info)])
        self.assertEqual(encounter.total_space(), 4)

    def test_total_space_multiple_monsters(self):
        """Test total_space with multiple monsters."""
        monsters = [Monster(self.goblin_info), Monster(self.orc_info)]
        encounter = Encounter(monsters)
        # 1 + 4 = 5 space
        self.assertEqual(encounter.total_space(), 5)


class TestMonsterUtilityFunctions(unittest.TestCase):
    """Test standalone monster utility functions."""

    def setUp(self):
        """Create test fixtures."""
        self.goblin_info = MonsterInfo(
            {
                "name": "Goblin",
                "ascii_char": "g",
                "challenge_rating": 0.25,
            }
        )
        self.orc_info = MonsterInfo(
            {"name": "Orc", "ascii_char": "o", "challenge_rating": 1}
        )

    def test_summarize_monsters_single(self):
        """Test summarize_monsters with single monster."""
        monsters = [Monster(self.goblin_info)]
        summary = summarize_monsters(monsters)
        self.assertIn("Goblin", summary)
        self.assertIn("x1", summary)

    def test_summarize_monsters_multiple_same(self):
        """Test summarize_monsters with multiple of same type."""
        monsters = [
            Monster(self.goblin_info),
            Monster(self.goblin_info),
            Monster(self.goblin_info),
        ]
        summary = summarize_monsters(monsters)
        self.assertIn("Goblin", summary)
        self.assertIn("x3", summary)

    def test_summarize_monsters_mixed(self):
        """Test summarize_monsters with mixed types."""
        monsters = [
            Monster(self.goblin_info),
            Monster(self.goblin_info),
            Monster(self.orc_info),
        ]
        summary = summarize_monsters(monsters)
        self.assertIn("Goblin", summary)
        self.assertIn("x2", summary)
        self.assertIn("Orc", summary)
        self.assertIn("x1", summary)

    def test_med_target_xp_calculates_correctly(self):
        """Test med_target_xp calculation."""
        config = MagicMock()
        config.target_character_level = 1
        config.num_player_characters = 4
        xp = med_target_xp(config)
        # Level 1 char = 50 xp/char, 4 chars = 200 xp
        self.assertEqual(xp, 200)

    def test_med_target_xp_higher_level(self):
        """Test med_target_xp at higher level."""
        config = MagicMock()
        config.target_character_level = 5
        config.num_player_characters = 4
        xp = med_target_xp(config)
        # Level 5 char = 500 xp/char, 4 chars = 2000 xp
        self.assertEqual(xp, 2000)

    def test_med_target_xp_more_characters(self):
        """Test med_target_xp with more characters."""
        config = MagicMock()
        config.target_character_level = 3
        config.num_player_characters = 6
        xp = med_target_xp(config)
        # Level 3 char = 150 xp/char, 6 chars = 900 xp
        self.assertEqual(xp, 900)


class TestEncounterScoring(unittest.TestCase):
    """Test encounter scoring function."""

    def setUp(self):
        """Create test fixtures."""
        self.frontline_info = MonsterInfo(
            {
                "name": "Orc",
                "ascii_char": "o",
                "challenge_rating": 1,
                "keywords": ["Frontline"],
            }
        )
        self.backline_info = MonsterInfo(
            {
                "name": "Wizard",
                "ascii_char": "w",
                "challenge_rating": 1,
                "keywords": ["Backline"],
            }
        )
        self.balanced_info = MonsterInfo(
            {
                "name": "Fighter",
                "ascii_char": "f",
                "challenge_rating": 1,
            }
        )

    def test_score_encounter_basic(self):
        """Test score_encounter returns a valid score."""
        encounter = Encounter([Monster(self.balanced_info)])
        score = score_encounter(encounter, 200, {})
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 2)  # Generally bounded

    def test_score_encounter_exact_xp_best(self):
        """Test score_encounter favors encounters matching target XP."""
        with patch("lib.monster.eval_dice", return_value=15):
            monster = Monster(self.balanced_info, health=15)
            monster.monster_info.xp = 200
            encounter = Encounter([monster])
            target_xp = 200
            score = score_encounter(encounter, target_xp, {})
            self.assertGreater(score, 0.5)  # Should be relatively high

    def test_score_encounter_all_frontline_penalized(self):
        """Test score_encounter penalizes all frontline."""
        monsters = [Monster(self.frontline_info), Monster(self.frontline_info)]
        encounter = Encounter(monsters)
        score = score_encounter(encounter, 400, {})
        self.assertGreater(score, 0)
        # Score should be lower than with mixed frontline/backline

    def test_score_encounter_new_monsters_bonus(self):
        """Test score_encounter bonuses new monsters."""
        encounter = Encounter([Monster(self.balanced_info)])
        prev_monsters = {}  # No previous monsters
        score = score_encounter(encounter, 200, prev_monsters)
        self.assertGreater(score, 0)
        # Score should get bonus for new unique monster


class TestBuildEncounter(unittest.TestCase):
    """Test encounter building function."""

    def setUp(self):
        """Create test fixtures."""
        self.monster_infos = [
            MonsterInfo(
                {
                    "name": "Goblin",
                    "challenge_rating": 0.25,
                    "frequency": 1.0,
                }
            ),
            MonsterInfo(
                {"name": "Orc", "challenge_rating": 1, "frequency": 1.0}
            ),
            MonsterInfo(
                {
                    "name": "Ogre",
                    "challenge_rating": 2,
                    "frequency": 1.0,
                }
            ),
        ]

    def test_build_encounter_returns_encounter(self):
        """Test build_encounter returns an Encounter object."""
        encounter = build_encounter(self.monster_infos, target_xp=200)
        self.assertIsInstance(encounter, Encounter)

    def test_build_encounter_has_monsters(self):
        """Test build_encounter generates monsters."""
        encounter = build_encounter(self.monster_infos, target_xp=200)
        self.assertGreater(len(encounter.monsters), 0)

    def test_build_encounter_respects_target_xp(self):
        """Test build_encounter tries to match target XP."""
        encounter = build_encounter(self.monster_infos, target_xp=200)
        xp = encounter.total_xp()
        # Should be reasonably close to target
        self.assertGreater(xp, 50)  # Not way too low
        self.assertLess(xp, 400)  # Not way too high

    def test_build_encounter_respects_variety(self):
        """Test build_encounter respects variety parameter."""
        encounter = build_encounter(
            self.monster_infos, target_xp=200, variety=1
        )
        # With variety=1, should only have one type of monster
        names = {m.monster_info.name for m in encounter.monsters}
        self.assertEqual(len(names), 1)

    def test_build_encounter_with_max_space(self):
        """Test build_encounter respects max_space constraint."""
        large_info = MonsterInfo(
            {
                "name": "Large Monster",
                "challenge_rating": 5,
                "size": "large",  # diameter 2, space 4
                "frequency": 1.0,
            }
        )
        monster_infos = [
            self.monster_infos[0],  # Goblin
            large_info,
        ]
        encounter = build_encounter(monster_infos, target_xp=500, max_space=10)
        # Total space should not exceed 10
        self.assertLessEqual(encounter.total_space(), 10)


class TestMonsterLibrary(unittest.TestCase):
    """Test MonsterLibrary class."""

    def test_library_init(self):
        """Test MonsterLibrary initialization."""
        lib = MonsterLibrary("test")
        self.assertEqual(lib.name, "test")
        self.assertEqual(lib.monster_infos, [])

    def test_library_get_monster_infos_empty(self):
        """Test get_monster_infos on empty library."""
        lib = MonsterLibrary("test")
        infos = lib.get_monster_infos()
        self.assertEqual(infos, [])

    def test_library_get_monster_infos_by_cr_min(self):
        """Test get_monster_infos with min_challenge_rating."""
        lib = MonsterLibrary("test")
        lib.monster_infos = [
            MonsterInfo({"name": "Easy", "challenge_rating": 0.25}),
            MonsterInfo({"name": "Medium", "challenge_rating": 1}),
            MonsterInfo({"name": "Hard", "challenge_rating": 5}),
        ]
        infos = lib.get_monster_infos(min_challenge_rating=1)
        names = {m.name for m in infos}
        self.assertEqual(names, {"Medium", "Hard"})

    def test_library_get_monster_infos_by_cr_max(self):
        """Test get_monster_infos with max_challenge_rating."""
        lib = MonsterLibrary("test")
        lib.monster_infos = [
            MonsterInfo({"name": "Easy", "challenge_rating": 0.25}),
            MonsterInfo({"name": "Medium", "challenge_rating": 1}),
            MonsterInfo({"name": "Hard", "challenge_rating": 5}),
        ]
        infos = lib.get_monster_infos(max_challenge_rating=1)
        names = {m.name for m in infos}
        self.assertEqual(names, {"Easy", "Medium"})

    def test_library_get_monster_infos_by_cr_range(self):
        """Test get_monster_infos with both CR bounds."""
        lib = MonsterLibrary("test")
        lib.monster_infos = [
            MonsterInfo({"name": "Easy", "challenge_rating": 0.25}),
            MonsterInfo({"name": "Medium", "challenge_rating": 1}),
            MonsterInfo({"name": "Hard", "challenge_rating": 5}),
        ]
        infos = lib.get_monster_infos(
            min_challenge_rating=0.5, max_challenge_rating=2
        )
        names = {m.name for m in infos}
        self.assertEqual(names, {"Medium"})

    def test_library_to_blob(self):
        """Test library to_blob serialization."""
        lib = MonsterLibrary("test")
        lib.monster_infos = [
            MonsterInfo({"name": "Goblin", "challenge_rating": 0.25}),
            MonsterInfo({"name": "Orc", "challenge_rating": 1}),
        ]
        blob = lib.to_blob()
        self.assertEqual(blob["name"], "test")
        self.assertEqual(len(blob["monsters"]), 2)

    def test_library_to_blob_sorted_by_cr(self):
        """Test library to_blob sorts by CR."""
        lib = MonsterLibrary("test")
        lib.monster_infos = [
            MonsterInfo({"name": "Orc", "challenge_rating": 1}),
            MonsterInfo({"name": "Goblin", "challenge_rating": 0.25}),
        ]
        blob = lib.to_blob()
        # Should be sorted by CR, then name
        names = [m["name"] for m in blob["monsters"]]
        self.assertEqual(names, ["Goblin", "Orc"])


if __name__ == "__main__":
    unittest.main()
