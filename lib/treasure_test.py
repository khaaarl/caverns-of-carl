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

from lib.treasure import Book, TreasureLibrary


class TestBook(unittest.TestCase):
    """Test Book class."""

    def setUp(self):
        """Create test fixtures."""
        self.book_obj = {
            "Title": "The Hobbit",
            "Author": "J.R.R. Tolkien",
            "Description": "A fantasy adventure",
            "Synopsis": "Bilbo's journey",
            "Excerpt": "In a hole in the ground there lived a hobbit.",
            "AuthorBackground": "British author",
            "Keywords": ["Fantasy", "Adventure"],
        }

    def test_init_from_object(self):
        """Test Book initialization from object."""
        book = Book(self.book_obj)
        self.assertEqual(book.title, "The Hobbit")
        self.assertEqual(book.author, "J.R.R. Tolkien")
        self.assertEqual(book.description, "A fantasy adventure")
        self.assertEqual(book.synopsis, "Bilbo's journey")

    def test_init_with_minimal_data(self):
        """Test Book with minimal data."""
        book = Book({"Title": "Minimal Book"})
        self.assertEqual(book.title, "Minimal Book")
        self.assertIsNone(book.author)
        self.assertIsNone(book.description)
        self.assertEqual(book.keywords, set())

    def test_init_with_no_keywords(self):
        """Test Book with no keywords."""
        book = Book({"Title": "Book", "Keywords": None})
        self.assertEqual(book.keywords, set())

    def test_init_with_keywords_list(self):
        """Test Book with keywords list."""
        book = Book(
            {"Title": "Book", "Keywords": ["Fantasy", "Adventure", "Magic"]}
        )
        self.assertEqual(book.keywords, {"Fantasy", "Adventure", "Magic"})

    def test_tts_nickname_with_author(self):
        """Test tts_nickname with author."""
        book = Book({"Title": "The Hobbit", "Author": "J.R.R. Tolkien"})
        nickname = book.tts_nickname()
        self.assertIn("The Hobbit", nickname)
        self.assertIn("J.R.R. Tolkien", nickname)
        self.assertIn("[u]", nickname)  # Underlined

    def test_tts_nickname_without_author(self):
        """Test tts_nickname without author."""
        book = Book({"Title": "Anonymous Book"})
        nickname = book.tts_nickname()
        self.assertIn("Anonymous Book", nickname)
        self.assertNotIn("by", nickname)

    def test_tts_description_all_fields(self):
        """Test tts_description with all fields."""
        book = Book(self.book_obj)
        desc = book.tts_description()
        self.assertIn("A fantasy adventure", desc)
        self.assertIn("Bilbo's journey", desc)
        self.assertIn("In a hole in the ground", desc)
        self.assertIn("British author", desc)

    def test_tts_description_only_title(self):
        """Test tts_description with only title."""
        book = Book({"Title": "Minimal"})
        desc = book.tts_description()
        self.assertEqual(desc, "")

    def test_tts_description_excerpt_italicized(self):
        """Test tts_description italicizes excerpt."""
        book = Book(
            {
                "Title": "Book",
                "Excerpt": "Quoted text",
            }
        )
        desc = book.tts_description()
        self.assertIn("[i]", desc)
        self.assertIn("Quoted text", desc)

    def test_tts_reference_nickname_humor_book(self):
        """Test tts_reference_nickname returns 'Comedy' for humor books."""
        book = Book(
            {
                "Title": "Funny Book",
                "Keywords": ["Humor"],
            }
        )
        nickname = book.tts_reference_nickname()
        self.assertEqual(nickname, "Reference Book Comedy")

    def test_tts_reference_nickname_non_humor_book(self):
        """Test tts_reference_nickname returns letter for non-humor books."""
        book = Book(
            {
                "Title": "Normal Book",
                "Keywords": ["Fantasy"],
            }
        )
        nickname = book.tts_reference_nickname()
        # Should be Reference Book followed by a letter A-J
        self.assertTrue(nickname.startswith("Reference Book "))
        letter = nickname.split()[-1]
        self.assertIn(letter, "ABCDEFGHIJ")

    def test_tts_reference_nickname_no_keywords(self):
        """Test tts_reference_nickname without keywords."""
        book = Book({"Title": "Book"})
        nickname = book.tts_reference_nickname()
        self.assertTrue(nickname.startswith("Reference Book "))
        letter = nickname.split()[-1]
        self.assertIn(letter, "ABCDEFGHIJ")

    def test_tts_object_has_nickname_and_description(self):
        """Test tts_object sets nickname and description."""
        with patch("lib.treasure.tts.reference_object") as mock_ref:
            mock_obj = {"Nickname": "", "Description": ""}
            mock_ref.return_value = mock_obj
            book = Book({"Title": "Test Book", "Author": "Author"})
            obj = book.tts_object()
            self.assertIn("Test Book", obj["Nickname"])
            # description should be set (could be empty if book has no fields)


class TestTreasureLibraryBasics(unittest.TestCase):
    """Test TreasureLibrary basic functionality."""

    def setUp(self):
        """Create test fixtures."""
        self.lib = TreasureLibrary("test")

    def test_init(self):
        """Test TreasureLibrary initialization."""
        self.assertEqual(self.lib.name, "test")
        self.assertEqual(self.lib.tables, [])
        self.assertEqual(self.lib.items, [])
        self.assertEqual(self.lib.variants, [])
        self.assertEqual(self.lib.art_objects, {})
        self.assertEqual(self.lib.gemstones, {})

    def test_to_blob(self):
        """Test to_blob returns self."""
        # Note: The actual to_blob implementation just returns self
        blob = self.lib.to_blob()
        self.assertIs(blob, self.lib)


class TestTreasureLibraryItemExpansion(unittest.TestCase):
    """Test TreasureLibrary item expansion."""

    def setUp(self):
        """Create test fixtures."""
        self.lib = TreasureLibrary("test")
        self.lib.items = [
            {
                "name": "Sword",
                "variants": None,
            },
            {
                "name": "Potion",
                "variants": ["Healing Potion", "Poison Potion"],
            },
        ]
        self.lib.variants = [
            {
                "name": "spell-lvl0",
                "variants": ["Fire Bolt", "Light", "Mage Hand"],
            },
            {
                "name": "color",
                "variants": ["Red", "Blue", "Green"],
            },
        ]

    def test_expand_item_no_variant(self):
        """Test expand_item with item that has no variants."""
        result = self.lib.expand_item("Sword")
        self.assertEqual(result, "Sword")

    def test_expand_item_with_variant_selection(self):
        """Test expand_item selects from variant list."""
        with patch("random.choice") as mock_choice:
            mock_choice.return_value = "Healing Potion"
            result = self.lib.expand_item("Potion")
            self.assertEqual(result, "Healing Potion")

    def test_expand_item_unknown_item(self):
        """Test expand_item with unknown item."""
        result = self.lib.expand_item("Unknown Item")
        self.assertEqual(result, "Unknown Item")

    def test_expand_variant_no_placeholders(self):
        """Test expand_variant with no placeholders."""
        result = self.lib.expand_variant("Simple Item")
        self.assertEqual(result, "Simple Item")

    def test_expand_variant_single_placeholder(self):
        """Test expand_variant with single placeholder."""
        with patch("random.choice") as mock_choice:
            mock_choice.return_value = "Fire Bolt"
            result = self.lib.expand_variant("Scroll of {spell-lvl0}")
            self.assertEqual(result, "Scroll of Fire Bolt")

    def test_expand_variant_multiple_placeholders(self):
        """Test expand_variant with multiple placeholders."""
        with patch("random.choice") as mock_choice:
            mock_choice.side_effect = ["Red", "Fire Bolt"]
            result = self.lib.expand_variant("{color} scroll of {spell-lvl0}")
            self.assertEqual(result, "Red scroll of Fire Bolt")

    def test_expand_variant_whitespace_in_placeholder(self):
        """Test expand_variant handles whitespace in placeholder."""
        with patch("random.choice") as mock_choice:
            mock_choice.return_value = "Fire Bolt"
            result = self.lib.expand_variant("Scroll of { spell-lvl0 }")
            self.assertEqual(result, "Scroll of Fire Bolt")

    def test_expand_variant_unknown_placeholder(self):
        """Test expand_variant with unknown placeholder leaves variant name."""
        # Unknown placeholders get the name extracted but stay as text
        result = self.lib.expand_variant("Scroll of {unknown}")
        # The actual behavior is to remove braces and use the name
        self.assertIn("unknown", result)


class TestTreasureLibraryRollOnTable(unittest.TestCase):
    """Test TreasureLibrary table rolling."""

    def setUp(self):
        """Create test fixtures."""
        self.lib = TreasureLibrary("test")
        self.lib.tables = [
            {
                "name": "Treasure Table",
                "table": [
                    ("1-50", "Common Item"),
                    ("51-75", "Rare Item"),
                    ("76-100", "Legendary Item"),
                ],
            }
        ]
        self.lib.items = []
        self.lib.variants = []

    def test_roll_on_table_case_insensitive(self):
        """Test roll_on_table is case-insensitive."""
        with patch("random.randrange", return_value=25):  # 1-50 range
            result = self.lib.roll_on_table("treasure table")
            self.assertEqual(result, "Common Item")

    def test_roll_on_table_in_first_range(self):
        """Test roll_on_table with result in first range."""
        with patch("random.randrange", return_value=30):  # 1-50 range
            result = self.lib.roll_on_table("Treasure Table")
            self.assertEqual(result, "Common Item")

    def test_roll_on_table_in_middle_range(self):
        """Test roll_on_table with result in middle range."""
        with patch("random.randrange", return_value=60):  # 51-75 range
            result = self.lib.roll_on_table("Treasure Table")
            self.assertEqual(result, "Rare Item")

    def test_roll_on_table_in_last_range(self):
        """Test roll_on_table with result in last range."""
        with patch("random.randrange", return_value=90):  # 76-100 range
            result = self.lib.roll_on_table("Treasure Table")
            self.assertEqual(result, "Legendary Item")

    def test_roll_on_table_not_found(self):
        """Test roll_on_table raises KeyError for missing table."""
        with self.assertRaises(KeyError):
            self.lib.roll_on_table("Nonexistent Table")

    def test_roll_on_table_exact_boundary(self):
        """Test roll_on_table on exact boundary."""
        with patch("random.randrange", return_value=50):  # Exactly 50
            result = self.lib.roll_on_table("Treasure Table")
            self.assertEqual(result, "Common Item")

    def test_roll_on_table_single_value_range(self):
        """Test roll_on_table with single-value range."""
        self.lib.tables = [
            {
                "name": "Test",
                "table": [
                    ("10", "Exact Item"),
                ],
            }
        ]
        with patch("random.randrange", return_value=10):
            result = self.lib.roll_on_table("Test")
            self.assertEqual(result, "Exact Item")


class TestTreasureLibraryGoldToTreasure(unittest.TestCase):
    """Test TreasureLibrary gold to treasure conversion."""

    def setUp(self):
        """Create test fixtures."""
        self.lib = TreasureLibrary("test")
        self.lib.gemstones = {
            100: ["Diamond", "Ruby"],
            50: ["Sapphire", "Emerald"],
            25: ["Garnet", "Topaz"],
        }
        self.lib.art_objects = {
            500: ["Gold Chalice", "Silver Crown"],
            200: ["Gold Statue", "Jeweled Box"],
        }

    def test_gold_to_treasure_returns_list_of_strings(self):
        """Test gold_to_treasure returns list of strings."""
        with patch("lib.treasure.random.choice") as mock_choice:
            # First call returns treasure type tuple, subsequent calls return item names
            def choice_side_effect(seq):
                if isinstance(seq, list) and len(seq) > 0:
                    if isinstance(seq[0], tuple):
                        # Treasure type choice
                        return ("Gemstone", self.lib.gemstones)
                    else:
                        # Item name choice
                        return seq[0] if seq else "Test Item"
                return seq[0] if seq else "Test Item"

            mock_choice.side_effect = choice_side_effect
            result = self.lib.gold_to_treasure(100)
            self.assertIsInstance(result, list)
            for item in result:
                self.assertIsInstance(item, str)

    def test_gold_to_treasure_with_small_amount(self):
        """Test gold_to_treasure with small gold amount."""
        with patch("lib.treasure.random.choice") as mock_choice:

            def choice_side_effect(seq):
                if isinstance(seq, list) and len(seq) > 0:
                    if isinstance(seq[0], tuple):
                        return ("Gemstone", self.lib.gemstones)
                    else:
                        return seq[0] if seq else "Item"
                return "Item"

            mock_choice.side_effect = choice_side_effect
            with patch("random.random", return_value=0.5):
                result = self.lib.gold_to_treasure(10)
                # Should return a list
                self.assertIsInstance(result, list)

    def test_gold_to_treasure_with_large_amount(self):
        """Test gold_to_treasure with large gold amount."""
        with patch("lib.treasure.random.choice") as mock_choice:

            def choice_side_effect(seq):
                if isinstance(seq, list) and len(seq) > 0:
                    if isinstance(seq[0], tuple):
                        return ("Art Object", self.lib.art_objects)
                    else:
                        return seq[0] if seq else "Gold Chalice"
                return "Gold Chalice"

            mock_choice.side_effect = choice_side_effect
            with patch("random.random", return_value=0.5):
                result = self.lib.gold_to_treasure(1500)
                # Should return a list
                self.assertIsInstance(result, list)

    def test_gold_to_treasure_returns_sorted(self):
        """Test gold_to_treasure returns sorted results."""
        with patch("lib.treasure.random.choice") as mock_choice:

            def choice_side_effect(seq):
                if isinstance(seq, list) and len(seq) > 0:
                    if isinstance(seq[0], tuple):
                        return ("Gemstone", self.lib.gemstones)
                    else:
                        return seq[0] if seq else "Item"
                return "Item"

            mock_choice.side_effect = choice_side_effect
            with patch("random.random", return_value=0.5):
                result = self.lib.gold_to_treasure(200)
                # Should be sorted
                self.assertEqual(result, sorted(result))


class TestTreasureLibraryHoardCalculation(unittest.TestCase):
    """Test TreasureLibrary hoard calculations."""

    def setUp(self):
        """Create test fixtures."""
        self.lib = TreasureLibrary("test")

    def test_hoard_gp_quantity_basic(self):
        """Test _hoard_gp_quantity calculates reasonable values."""
        with patch("random.random", return_value=0.5):
            # Random value of 0.5 means no variance
            gp = self.lib._hoard_gp_quantity(level=5, num_player_characters=4)
            self.assertGreater(gp, 0)

    def test_hoard_gp_quantity_increases_with_level(self):
        """Test _hoard_gp_quantity increases with level."""
        with patch("random.random", return_value=0.5):
            gp_level_1 = self.lib._hoard_gp_quantity(
                level=1, num_player_characters=4
            )
            gp_level_10 = self.lib._hoard_gp_quantity(
                level=10, num_player_characters=4
            )
            self.assertLess(gp_level_1, gp_level_10)

    def test_hoard_gp_quantity_increases_with_party_size(self):
        """Test _hoard_gp_quantity increases with party size."""
        with patch("random.random", return_value=0.5):
            gp_solo = self.lib._hoard_gp_quantity(
                level=5, num_player_characters=1
            )
            gp_party = self.lib._hoard_gp_quantity(
                level=5, num_player_characters=4
            )
            self.assertLess(gp_solo, gp_party)

    def test_hoard_gp_quantity_variance(self):
        """Test _hoard_gp_quantity varies with random."""
        # random.random() = 0 gives low variance
        # random.random() = 1 gives high variance
        with patch("random.random") as mock_rand:
            mock_rand.return_value = 0.0  # level + 3*(-1) = level - 3
            gp_low = self.lib._hoard_gp_quantity(
                level=5, num_player_characters=4
            )
            mock_rand.return_value = 1.0  # level + 3*(1) = level + 3
            gp_high = self.lib._hoard_gp_quantity(
                level=5, num_player_characters=4
            )
            self.assertLess(gp_low, gp_high)


class TestTreasureLibraryGenHorde(unittest.TestCase):
    """Test TreasureLibrary horde generation."""

    def test_gen_horde_hoard_gp_positive(self):
        """Test _hoard_gp_quantity returns positive values."""
        lib = TreasureLibrary("test")
        with patch("random.random", return_value=0.5):
            gp = lib._hoard_gp_quantity(level=5, num_player_characters=4)
            self.assertGreater(gp, 0)


class TestTreasureLibraryGenBookshelfHorde(unittest.TestCase):
    """Test TreasureLibrary bookshelf horde generation."""

    def setUp(self):
        """Create test fixtures."""
        self.lib = TreasureLibrary("test")
        self.lib.items = []
        self.lib.variants = [
            {
                "name": "spell-lvl0",
                "variants": ["Fire Bolt"],
            }
        ]

    def test_gen_bookshelf_horde_returns_list(self):
        """Test gen_bookshelf_horde returns a list."""
        with patch("lib.treasure.random.randrange", return_value=999):
            with patch(
                "lib.treasure.random.choice", return_value="Spell scroll"
            ):
                with patch("lib.treasure.eval_dice", return_value=2):
                    result = self.lib.gen_bookshelf_horde(
                        level=5, num_player_characters=4
                    )
                    self.assertIsInstance(result, list)

    def test_gen_bookshelf_horde_respects_max_size(self):
        """Test gen_bookshelf_horde respects maximum size."""
        with patch("lib.treasure.random.randrange", return_value=999):
            with patch(
                "lib.treasure.random.choice", return_value="Spell scroll"
            ):
                with patch("lib.treasure.eval_dice") as mock_dice:
                    # First call: max_size, second call: 1d4-1 for books
                    mock_dice.side_effect = [2, 0]
                    result = self.lib.gen_bookshelf_horde(
                        level=5, num_player_characters=4
                    )
                    # Should not exceed eval_dice result (2 in this case)
                    self.assertLessEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
