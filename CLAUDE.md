# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Caverns of Carl is a D&D 5e random dungeon generator with a Tkinter GUI. It outputs Tabletop Simulator (TTS) save files, PDF documents, and 2D map images (PNG).

## Commands

```bash
# Run the application (requires tkinter / display)
python caverns_of_carl.py

# Run tests
python -m unittest lib.utils_test

# Regenerate tile sprite PNGs (standalone, no tkinter needed)
python -m lib.generate_tiles

# Formatting (enforced by pre-commit hooks)
black --line-length=79 .
isort --profile=black --line-length=79 .

# Pre-commit (runs black + isort)
pre-commit run --all-files

# Install dependencies
pip install -r requirements.txt         # runtime: reportlab, pillow
pip install -r requirements-dev.txt     # dev: black, isort, pre-commit, ruff, ty
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

- Only `lib/utils_test.py` exists (keyword expression parser tests).
- Tkinter is unavailable in headless environments. To test code that imports config, mock tkinter with `types.ModuleType('tkinter')` and stub `StringVar`, `IntVar`, `DoubleVar`, `BooleanVar`.
- `lib/generate_tiles.py` and `lib/map_image.py` work without tkinter.

## Data Files

- `reference_info/monsters/dnd 5e monsters.json`: D&D 5e monster library
- `reference_info/treasure/`, `reference_info/npcs/`, `reference_info/misc/`: game data tables (JSON)
- `reference_info/tiles/`: generated 64x64 PNG tile sprites
- `output/`: generated files (maps, PDFs) - gitignored
