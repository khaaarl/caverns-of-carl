"""
Produces a 2D map image from a DungeonFloor by compositing tile images.
Output is suitable for use in 2D virtual tabletops like Roll20.
"""

import os
import random

from PIL import Image

from lib.tile import (
    BookshelfTile,
    ChestTile,
    CorridorFloorTile,
    DoorTile,
    LadderDownTile,
    LadderUpTile,
    MimicTile,
    RoomFloorTile,
    SecretDoorTile,
    WallTile,
    WaterTile,
)
from lib.utils import COC_ROOT_DIR

TILE_SIZE = 64
TILES_DIR = os.path.join(COC_ROOT_DIR, "reference_info", "tiles")
OUTPUT_DIR = os.path.join(COC_ROOT_DIR, "output", "maps")

# Cache for loaded tile images
_tile_image_cache = {}


def _load_tile(name):
    """Load a tile image by name, with caching. Preserves alpha if present."""
    if name not in _tile_image_cache:
        path = os.path.join(TILES_DIR, f"{name}.png")
        img = Image.open(path)
        # Keep RGBA if it has alpha, otherwise convert to RGB
        if img.mode == "RGBA":
            _tile_image_cache[name] = img
        else:
            _tile_image_cache[name] = img.convert("RGB")
    return _tile_image_cache[name]


def _door_tile_name(df, x, y):
    """Determine the correct door tile image name based on orientation,
    width (how many adjacent door tiles), and position within the group.

    Scans both E-W and N-S for adjacent DoorTiles first, then infers
    orientation from the scan results (not from neighboring floor tiles,
    which can be misleading when rooms extend alongside corridors).
    """
    # Scan E-W for adjacent DoorTiles
    ew_min = x
    while isinstance(df.get_tile(ew_min - 1, y), DoorTile):
        ew_min -= 1
    ew_max = x
    while isinstance(df.get_tile(ew_max + 1, y), DoorTile):
        ew_max += 1
    ew_width = ew_max - ew_min + 1

    # Scan N-S for adjacent DoorTiles
    ns_min = y
    while isinstance(df.get_tile(x, ns_min - 1), DoorTile):
        ns_min -= 1
    ns_max = y
    while isinstance(df.get_tile(x, ns_max + 1), DoorTile):
        ns_max += 1
    ns_width = ns_max - ns_min + 1

    if ew_width > 1 and ns_width == 1:
        # Door group spans E-W → passage goes N-S → "horizontal"
        pos = x - ew_min
        if ew_width == 2:
            part = "left" if pos == 0 else "right"
            return f"door_horizontal_2_{part}"
        elif ew_width >= 3:
            if pos == 0:
                return "door_horizontal_3_left"
            elif pos == ew_width - 1:
                return "door_horizontal_3_right"
            else:
                return "door_horizontal_3_center"

    if ns_width > 1 and ew_width == 1:
        # Door group spans N-S → passage goes E-W → "vertical"
        # Image y is flipped: dungeon north (high y) = image top
        pos = ns_max - y  # 0 = top (highest y)
        if ns_width == 2:
            part = "top" if pos == 0 else "bottom"
            return f"door_vertical_2_{part}"
        elif ns_width >= 3:
            if pos == 0:
                return "door_vertical_3_top"
            elif pos == ns_width - 1:
                return "door_vertical_3_bottom"
            else:
                return "door_vertical_3_center"

    # Single-tile door: determine orientation by checking which direction
    # has non-wall, non-door tiles (i.e. where the passage goes)
    def is_passage(tx, ty):
        tile = df.get_tile(tx, ty)
        return tile is not None and not isinstance(tile, (WallTile, DoorTile))

    ns_passage = is_passage(x, y + 1) or is_passage(x, y - 1)
    ew_passage = is_passage(x + 1, y) or is_passage(x - 1, y)

    if ew_passage and not ns_passage:
        return "door_vertical"
    return "door_horizontal"


def _select_floor_image(tile, rng):
    """Select the floor image appropriate for this tile's location."""
    if tile.tile_style == "cavern":
        variant = rng.randint(0, 5)
        return _load_tile(f"cavern_floor_{variant}")
    if isinstance(tile, CorridorFloorTile):
        variant = rng.randint(0, 1)
        return _load_tile(f"corridor_{variant}")
    variant = rng.randint(0, 2)
    return _load_tile(f"floor_{variant}")


# Tile types that are RGBA overlays composited on top of the floor
_OVERLAY_TYPES = (
    ChestTile,
    BookshelfTile,
    MimicTile,
    LadderUpTile,
    LadderDownTile,
)


def _select_wall_image(tile):
    """Select the appropriate wall image for a wall tile."""
    if tile.tile_style == "cavern":
        return _load_tile("cavern_wall"), None
    return _load_tile("wall"), None


def _select_tile_image(tile, df, player_map=False):
    """Select the appropriate tile image for a given tile.

    Returns (floor_img, overlay_img) where overlay_img may be None.
    If player_map is True, mimics appear as chests and secret doors as walls.
    """
    rng = random.Random(hash((tile.x, tile.y)))

    if isinstance(tile, WaterTile):
        variant = rng.randint(0, 2)
        return _load_tile(f"water_{variant}"), None

    if isinstance(tile, LadderUpTile):
        return _select_floor_image(tile, rng), _load_tile("ladder_up")

    if isinstance(tile, LadderDownTile):
        return _select_floor_image(tile, rng), _load_tile("ladder_down")

    if isinstance(tile, MimicTile):
        overlay = "chest" if player_map else "mimic"
        return _select_floor_image(tile, rng), _load_tile(overlay)

    if isinstance(tile, BookshelfTile):
        return _select_floor_image(tile, rng), _load_tile("bookshelf")

    if isinstance(tile, ChestTile):
        return _select_floor_image(tile, rng), _load_tile("chest")

    if isinstance(tile, SecretDoorTile):
        if player_map:
            return _select_wall_image(tile)
        return _load_tile("secret_door"), None

    if isinstance(tile, DoorTile):
        return _load_tile(_door_tile_name(df, tile.x, tile.y)), None

    if isinstance(tile, CorridorFloorTile):
        return _select_floor_image(tile, rng), None

    if isinstance(tile, RoomFloorTile):
        return _select_floor_image(tile, rng), None

    if isinstance(tile, WallTile):
        return _select_wall_image(tile)

    # Fallback
    return _load_tile("wall"), None


def produce_map_image(df, name, format="png", player_map=False):
    """Produce a 2D map image from a DungeonFloor.

    Args:
        df: DungeonFloor instance
        name: base name for the output file
        format: "png" or "jpg"
        player_map: if True, hide mimics (show as chests) and secret doors (show as walls)

    Returns:
        The output file path, or None if generation failed.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    width_px = df.width * TILE_SIZE
    height_px = df.height * TILE_SIZE
    map_img = Image.new("RGB", (width_px, height_px), color=(30, 30, 32))

    # The dungeon grid has (0,0) at bottom-left, but image (0,0) is top-left.
    # tile_iter goes from top to bottom (y from height-1 down to 0),
    # so we need to flip y when placing tiles.
    for x in range(df.width):
        for y in range(df.height):
            tile = df.tiles[x][y]
            floor_img, overlay_img = _select_tile_image(tile, df, player_map)
            # Flip y: dungeon y=0 is bottom, image y=0 is top
            img_x = x * TILE_SIZE
            img_y = (df.height - 1 - y) * TILE_SIZE
            map_img.paste(floor_img, (img_x, img_y))
            if overlay_img is not None:
                map_img.paste(overlay_img, (img_x, img_y), mask=overlay_img)

    ext = "jpg" if format.lower() in ("jpg", "jpeg") else "png"
    safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in name)
    suffix = " (player)" if player_map else " (DM)"
    filename = os.path.join(OUTPUT_DIR, f"{safe_name}{suffix}.{ext}")

    if ext == "jpg":
        map_img.save(filename, "JPEG", quality=92)
    else:
        map_img.save(filename, "PNG")

    return filename


def produce_dm_overlay_image(df, name, format="png"):
    """Produce a transparent overlay showing only mimics and secret doors.

    Mimics are rendered as just the mimic sprite (no floor underneath).
    Secret doors are rendered as the full secret door tile.
    Everything else is fully transparent.

    Args:
        df: DungeonFloor instance
        name: base name for the output file
        format: "png" (must be png to support transparency)

    Returns:
        The output file path, or None if generation failed.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    width_px = df.width * TILE_SIZE
    height_px = df.height * TILE_SIZE
    overlay_img = Image.new("RGBA", (width_px, height_px), (0, 0, 0, 0))

    for x in range(df.width):
        for y in range(df.height):
            tile = df.tiles[x][y]
            img_x = x * TILE_SIZE
            img_y = (df.height - 1 - y) * TILE_SIZE

            if isinstance(tile, MimicTile):
                mimic_img = _load_tile("mimic")
                overlay_img.paste(mimic_img, (img_x, img_y), mask=mimic_img)
            elif isinstance(tile, SecretDoorTile):
                secret_img = _load_tile("secret_door")
                overlay_img.paste(secret_img, (img_x, img_y))

    safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in name)
    filename = os.path.join(OUTPUT_DIR, f"{safe_name} (DM overlay).png")
    overlay_img.save(filename, "PNG")
    return filename


def produce_map_images_if_possible(df, name, format="png"):
    """Produce DM, player, and DM overlay map images. Returns list of created file paths."""
    results = []
    for player_map in [False, True]:
        try:
            path = produce_map_image(df, name, format, player_map=player_map)
            results.append(path)
        except Exception as e:
            label = "player" if player_map else "DM"
            print(f"Failed to produce {label} map image: {e}")
    try:
        path = produce_dm_overlay_image(df, name, format)
        results.append(path)
    except Exception as e:
        print(f"Failed to produce DM overlay image: {e}")
    return results
