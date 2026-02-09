# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Caverns of Carl is a D&D 5e random dungeon generator with a Tkinter GUI. It outputs Tabletop Simulator (TTS) save files, PDF documents, and 2D map images (PNG).

## Commands

```bash
# Run the application (requires tkinter / display)
python caverns_of_carl.py

# Run tests
python -m unittest lib.dungeon_test -v     # New: comprehensive dungeon tests (45 tests)
python -m unittest lib.utils_test -v       # Existing: keyword expression tests
python -m unittest discover -s lib -p "*_test.py" -v  # Run all tests

# Check test coverage
python -m coverage run -m unittest discover -s lib -p "*_test.py"
python -m coverage report lib/dungeon.py   # Report for specific module
python -m coverage html                    # Generate HTML report in htmlcov/

# Regenerate tile sprite PNGs (standalone, no tkinter needed)
python -m lib.generate_tiles

# Formatting (enforced by pre-commit hooks)
black --line-length=79 .
isort --profile=black --line-length=79 .

# Pre-commit (runs black + isort)
pre-commit run --all-files

# Install dependencies
pip install -r requirements.txt         # runtime: reportlab, pillow
pip install -r requirements-dev.txt     # dev: black, isort, pre-commit, ruff, ty, coverage
```

## Architecture

### Entry Point & UI
- `caverns_of_carl.py` → `lib/ui.py:run_ui()` launches a 3-pane Tkinter window (config, ASCII map, info/logs)
- `lib/config.py`: `DungeonConfig` manages all parameters as tkinter vars. Supports biomes (sub-configs with directional weighting). Auto-generates UI widgets from variable definitions.

### Dungeon Generation Pipeline
`lib/dungeon.py` orchestrates generation in a fixed pipeline order:
1. Biomes → rooms → erosion (cavernous) → corridors → rivers → doors → ladders
2. Special features → treasure → monsters → traps → lights → tile styling → NPCs

`DungeonFloor` is the central data structure holding `tiles[x][y]`, rooms, corridors, monsters, etc.

### Coordinate System
- `tiles[x][y]`: x is horizontal, y is vertical. **y=0 is the bottom** (south).
- Images flip Y: dungeon `y` maps to pixel row `(height - 1 - y)`.

### Tile Hierarchy
`lib/tile.py` defines tile types: `WallTile`, `RoomFloorTile`, `CorridorFloorTile`, `DoorTile`, `SecretDoorTile`, `WaterTile`, `ChestTile`, `BookshelfTile`, `MimicTile`, `LadderUpTile`, `LadderDownTile`. `DoorTile` extends `CorridorFloorTile`; `ChestTile` extends `RoomFloorTile`.

### Room Types
`lib/room.py`: `RectRoom` (standard), `CavernousRoom` (eroded irregular), `MazeJunction`.

### Output Generators
- `lib/tts.py`: TTS JSON save files with hidden zones, notecards, fog of war
- `lib/pdf.py`: ReportLab PDF with room descriptions, monster details, bookmarks
- `lib/map_image.py`: Composites 64x64 tile PNGs into full dungeon map. Generates player version (mimics hidden, secret doors hidden) and DM version.
- `lib/generate_tiles.py`: Procedurally generates the 64x64 tile sprite PNGs in `reference_info/tiles/`

### Utilities (`lib/utils.py`)
- `eval_dice()`: D&D dice notation parser (e.g. "2d6+3")
- Keyword expression parser (BNF-based, supports AND/OR/NOT/parentheses) for monster/treasure filters
- `bfs()`, `dfs()` for dungeon connectivity
- `WeightTreeNode` for efficient weighted random selection
- `COC_ROOT_DIR`: project root path constant

### Key Patterns
- **Retriable exceptions**: `RetriableDungeonographyException` and subclasses allow the generation pipeline to retry placement steps on failure.
- **Biome system**: Per-biome config overrides with directional weighting for region placement.
- **Styled text**: `StyledString`/`StyledChar`/`CharStyle` for colored text output in UI and PDF.

## Testing Notes

### Test Files
- `lib/dungeon_test.py` (NEW): Comprehensive unit tests for `lib/dungeon.py`
  - 45 tests across 7 test classes
  - Covers: room generation, room/corridor addition, tile operations, monster placement, ASCII output
  - Uses `unittest.mock.patch` to mock randomness for deterministic testing
- `lib/utils_test.py`: Existing tests for keyword expression parser

### Running Tests
```bash
# Run all dungeon tests
python -m unittest lib.dungeon_test -v

# Run specific test class
python -m unittest lib.dungeon_test.TestDungeonFloorRandomRoom -v

# Run single test
python -m unittest lib.dungeon_test.TestDungeonFloorRandomRoom.test_random_room_returns_room_object
```

### Headless Testing & Tkinter Mocking
Tkinter is unavailable in CI/headless environments. Both test files handle this:
- `lib/dungeon_test.py` includes `mock_tkinter()` function that creates minimal mocks for:
  - `StringVar`, `IntVar`, `DoubleVar`, `BooleanVar` (get/set methods)
  - UI classes: `Label`, `Frame`, `Button`, `Entry`, `Text`, `Canvas`, etc.
  - `tkinter.ttk.Combobox` and `tkinter.font`
- Call `mock_tkinter()` before importing `lib.config` to ensure mocks are in place
- Pattern: See top of `lib/dungeon_test.py` for example

### Test Organization
Tests follow the naming pattern: `lib/{module}_test.py` parallel to `lib/{module}.py`
- `lib/utils.py` → `lib/utils_test.py` (existing)
- `lib/dungeon.py` → `lib/dungeon_test.py` (new)
- Use `unittest.TestCase` as base class with `setUp()` for fixtures

### Test Coverage (Current)
- **lib/dungeon.py**: 15% (155 / 1,028 statements)
- **Overall project**: 24% (1,362 / 5,688 statements)
- Run `python -m coverage report lib/dungeon.py` to check coverage

### Random Number Mocking
Tests that need deterministic behavior use `@patch` decorator:
```python
from unittest.mock import patch

# Mock random.randrange() for specific coordinate selection
with patch("random.randrange") as mock_randrange:
    mock_randrange.side_effect = [10, 10]  # Returns (10, 10) for next calls
    room = dungeon.random_room()

# Mock random.random() for probability-based choices
with patch("random.random") as mock_random:
    mock_random.return_value = 0.25  # Returns 0.25 for next call
    room = dungeon.random_room()
```

### Modules Without Tests
- `lib/generate_tiles.py` and `lib/map_image.py` are standalone and can run without GUI
- UI code (`lib/ui.py`) is difficult to test; focus on testing business logic in dungeon.py, room.py, etc.
- Output generators (`lib/tts.py`, `lib/pdf.py`) tested manually; consider integration tests later

## Branching (CRITICAL — DO THIS FIRST)

**NEVER make code changes directly on `main`.** Before writing ANY code, you MUST:

1. Create a feature branch: `git checkout -b <descriptive-branch-name>`
2. Verify you are on the feature branch: `git branch --show-current`
3. ONLY THEN start making changes

**This is non-negotiable.** If you realize you are on `main` and have already made changes, STOP immediately and ask the user how to proceed — do NOT commit to `main`.

The only exception is editing `CLAUDE.md` itself, which can be done on `main` if explicitly requested. However, do NOT commit or push CLAUDE.md changes until the user explicitly says to — they may want to review or iterate first.

## Committing Code

ALWAYS ASK FOR PERMISSION BEFORE COMMITTING TO MAIN/MASTER, BUT COMMITTING TO FEATURE BRANCHES DOES NOT REQUIRE PERMISSION.

## Merging to Main

When the user asks to merge a feature branch to main, follow this procedure:

```bash
# 1. Create a temporary branch and squash all feature commits into one
#    (This way conflicts only need to be resolved once, not per-commit)
#    IMPORTANT: The REAL commit message goes HERE — step 4 is a fast-forward
#    merge which does NOT create a new commit, so any -m there is ignored.
git checkout -b feature/my-branch-rebase feature/my-branch
git reset --soft $(git merge-base main feature/my-branch-rebase)
git commit -m "Your descriptive commit message here"

# 2. Pull latest main
git checkout main && git pull

# 3. Rebase the single squashed commit onto main (conflict detection here)
git checkout feature/my-branch-rebase
git rebase main
# If conflicts arise, resolve them carefully, then: git add <files> && git rebase --continue

# 4. Fast-forward merge into main (no new commit — just moves the pointer)
git checkout main
git merge feature/my-branch-rebase

# 5. Push and clean up
git push
git branch -d feature/my-branch-rebase
```

**Why squash first, then rebase?** Rebasing a multi-commit branch onto main can require resolving the same conflict repeatedly (once per commit). By squashing into one commit first, you only resolve conflicts once. The `git reset --soft $(git merge-base ...)` in step 1 is safe — it collapses our own feature commits back to the branch point, without touching main's state. The rebase in step 3 then does proper 3-way conflict detection against latest main.

**Handling rebase conflicts:** When `git rebase main` reports conflicts:
1. Run `git status` to see which files conflict
2. Read the conflicting files — look for `<<<<<<<`, `=======`, `>>>>>>>` markers
3. Resolve by editing to keep the correct version of each section
4. `git add <resolved-files> && git rebase --continue`
5. After rebase completes, verify the code still works (run tests)
6. **If conflicts required non-trivial edits** (e.g., integrating two features that touch the same code), ask the user for permission before completing the merge. Truly trivial conflicts (e.g., both sides added adjacent lines with no semantic interaction) can be resolved and merged without asking.

The squashed commit message should summarize the entire feature, not repeat individual commit messages. Always ask the user before pushing to main.

## Data Files

- `reference_info/monsters/dnd 5e monsters.json`: D&D 5e monster library
- `reference_info/treasure/`, `reference_info/npcs/`, `reference_info/misc/`: game data tables (JSON)
- `reference_info/tiles/`: generated 64x64 PNG tile sprites
- `output/`: generated files (maps, PDFs) - gitignored
