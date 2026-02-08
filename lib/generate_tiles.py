"""
Generates programmatic placeholder tile images (64x64 PNGs) for 2D map output.
Run directly to regenerate: python -m lib.generate_tiles
"""

import os
import random

from PIL import Image, ImageDraw

TILE_SIZE = 64
TILES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
    "reference_info",
    "tiles",
)

# Color palettes
WALL_COLOR = (60, 60, 65)
WALL_LINE_COLOR = (80, 80, 85)
WALL_EDGE_COLOR = (90, 90, 95)
FLOOR_COLOR = (160, 140, 110)
FLOOR_LINE_COLOR = (145, 125, 100)
CORRIDOR_COLOR = (140, 120, 95)
CORRIDOR_LINE_COLOR = (125, 108, 85)
DOOR_COLOR = (120, 75, 40)
DOOR_FRAME_COLOR = (80, 80, 85)
WATER_COLOR = (40, 80, 160)
WATER_HIGHLIGHT = (70, 120, 190)
CHEST_COLOR = (170, 130, 50)
CHEST_DARK = (130, 95, 30)
BOOKSHELF_COLOR = (100, 60, 30)
BOOKSHELF_BOOK_COLORS = [
    (180, 40, 40),
    (40, 100, 40),
    (40, 40, 160),
    (160, 140, 40),
    (130, 50, 130),
]
LADDER_COLOR = (140, 100, 50)
LADDER_DARK = (100, 70, 35)
SECRET_MARK_COLOR = (110, 100, 100)
CAVERN_WALL_COLOR = (85, 75, 55)
CAVERN_WALL_DARK = (65, 55, 40)
CAVERN_FLOOR_COLOR = (135, 120, 90)
CAVERN_FLOOR_DARK = (120, 105, 78)


def _draw_stone_pattern(draw, color, line_color):
    """Draw a stone block pattern for walls/floors."""
    draw.rectangle([0, 0, TILE_SIZE, TILE_SIZE], fill=color)
    # Horizontal mortar lines
    for y in [16, 32, 48]:
        draw.line([(0, y), (TILE_SIZE, y)], fill=line_color, width=1)
    # Vertical mortar lines, offset every other row
    for row, y_start in enumerate([0, 16, 32, 48]):
        offset = 8 if row % 2 else 0
        for x in range(offset, TILE_SIZE, 16):
            draw.line(
                [(x, y_start), (x, y_start + 16)], fill=line_color, width=1
            )


def _draw_floor_texture(draw, base_color, line_color):
    """Draw a subtle flagstone floor pattern."""
    draw.rectangle([0, 0, TILE_SIZE, TILE_SIZE], fill=base_color)
    # Subtle grid of flagstones
    for x in [0, 32]:
        draw.line([(x, 0), (x, TILE_SIZE)], fill=line_color, width=1)
    for y in [0, 32]:
        draw.line([(0, y), (TILE_SIZE, y)], fill=line_color, width=1)
    # A few random speckles for texture
    rng = random.Random(42)
    for _ in range(12):
        sx = rng.randint(2, TILE_SIZE - 3)
        sy = rng.randint(2, TILE_SIZE - 3)
        r, g, b = base_color
        dr = rng.randint(-15, 15)
        speckle = (r + dr, g + dr, b + dr)
        draw.point((sx, sy), fill=speckle)


def _draw_cavern_floor_texture(draw, variant=0):
    """Draw a rough cavern floor with variant-specific randomization."""
    # Slightly shift base color per variant
    base_offsets = [0, 5, -5, 3, -3, 7]
    d = base_offsets[variant % len(base_offsets)]
    base = (
        CAVERN_FLOOR_COLOR[0] + d,
        CAVERN_FLOOR_COLOR[1] + d,
        CAVERN_FLOOR_COLOR[2] + d,
    )
    dark = (
        CAVERN_FLOOR_DARK[0] + d,
        CAVERN_FLOOR_DARK[1] + d,
        CAVERN_FLOOR_DARK[2] + d,
    )
    draw.rectangle([0, 0, TILE_SIZE, TILE_SIZE], fill=base)
    rng = random.Random(99 + variant * 137)
    # Scattered speckles
    for _ in range(rng.randint(15, 30)):
        sx = rng.randint(1, TILE_SIZE - 2)
        sy = rng.randint(1, TILE_SIZE - 2)
        dr = rng.randint(-20, 10)
        draw.point((sx, sy), fill=(base[0] + dr, base[1] + dr, base[2] + dr))
    # Irregular dark patches (varying count and size)
    num_patches = rng.randint(2, 5)
    for _ in range(num_patches):
        cx = rng.randint(8, TILE_SIZE - 8)
        cy = rng.randint(8, TILE_SIZE - 8)
        rx = rng.randint(3, 9)
        ry = rng.randint(3, 9)
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=dark)
    # Occasional small pebbles (light spots)
    for _ in range(rng.randint(0, 4)):
        px = rng.randint(4, TILE_SIZE - 4)
        py = rng.randint(4, TILE_SIZE - 4)
        pr = rng.randint(1, 3)
        lighter = (base[0] + 15, base[1] + 15, base[2] + 10)
        draw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=lighter)


def generate_wall():
    img = Image.new("RGB", (TILE_SIZE, TILE_SIZE))
    draw = ImageDraw.Draw(img)
    _draw_stone_pattern(draw, WALL_COLOR, WALL_LINE_COLOR)
    return img


def generate_wall_interior():
    """Solid dark wall for tiles completely surrounded by other walls."""
    img = Image.new("RGB", (TILE_SIZE, TILE_SIZE))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, TILE_SIZE, TILE_SIZE], fill=(30, 30, 32))
    return img


def generate_wall_edge(side):
    """Wall tile with a visible edge on one or more sides facing floor.
    side is a string like 'n', 's', 'e', 'w', 'ne', 'nw', etc.
    """
    img = generate_wall()
    draw = ImageDraw.Draw(img)
    edge_width = 3
    if "n" in side:
        draw.rectangle(
            [0, 0, TILE_SIZE - 1, edge_width - 1], fill=WALL_EDGE_COLOR
        )
    if "s" in side:
        draw.rectangle(
            [0, TILE_SIZE - edge_width, TILE_SIZE - 1, TILE_SIZE - 1],
            fill=WALL_EDGE_COLOR,
        )
    if "w" in side:
        draw.rectangle(
            [0, 0, edge_width - 1, TILE_SIZE - 1], fill=WALL_EDGE_COLOR
        )
    if "e" in side:
        draw.rectangle(
            [TILE_SIZE - edge_width, 0, TILE_SIZE - 1, TILE_SIZE - 1],
            fill=WALL_EDGE_COLOR,
        )
    return img


def generate_floor(variant=0):
    img = Image.new("RGB", (TILE_SIZE, TILE_SIZE))
    draw = ImageDraw.Draw(img)
    # Slightly vary the base color per variant
    r, g, b = FLOOR_COLOR
    offsets = [0, 5, -5]
    d = offsets[variant % len(offsets)]
    _draw_floor_texture(draw, (r + d, g + d, b + d), FLOOR_LINE_COLOR)
    return img


def generate_corridor(variant=0):
    img = Image.new("RGB", (TILE_SIZE, TILE_SIZE))
    draw = ImageDraw.Draw(img)
    r, g, b = CORRIDOR_COLOR
    offsets = [0, 4, -4]
    d = offsets[variant % len(offsets)]
    _draw_floor_texture(draw, (r + d, g + d, b + d), CORRIDOR_LINE_COLOR)
    return img


def generate_cavern_wall():
    img = Image.new("RGB", (TILE_SIZE, TILE_SIZE))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, TILE_SIZE, TILE_SIZE], fill=CAVERN_WALL_COLOR)
    rng = random.Random(77)
    # Rough rocky texture
    for _ in range(25):
        sx = rng.randint(0, TILE_SIZE - 1)
        sy = rng.randint(0, TILE_SIZE - 1)
        r, g, b = CAVERN_WALL_COLOR
        dr = rng.randint(-20, 15)
        draw.point((sx, sy), fill=(r + dr, g + dr, b + dr))
    for _ in range(4):
        cx = rng.randint(5, TILE_SIZE - 5)
        cy = rng.randint(5, TILE_SIZE - 5)
        r = rng.randint(4, 10)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=CAVERN_WALL_DARK)
    return img


def generate_cavern_floor(variant=0):
    img = Image.new("RGB", (TILE_SIZE, TILE_SIZE))
    draw = ImageDraw.Draw(img)
    _draw_cavern_floor_texture(draw, variant)
    return img


def generate_door_horizontal():
    """Door oriented for east-west passage (vertical wall opening)."""
    img = generate_floor()
    draw = ImageDraw.Draw(img)
    # Door frame (sides)
    draw.rectangle([0, 0, TILE_SIZE - 1, 6], fill=DOOR_FRAME_COLOR)
    draw.rectangle(
        [0, TILE_SIZE - 7, TILE_SIZE - 1, TILE_SIZE - 1], fill=DOOR_FRAME_COLOR
    )
    # Door plank
    draw.rectangle([8, 7, TILE_SIZE - 9, TILE_SIZE - 8], fill=DOOR_COLOR)
    # Plank lines
    for x in [20, 32, 44]:
        draw.line([(x, 8), (x, TILE_SIZE - 9)], fill=CHEST_DARK, width=1)
    # Handle
    draw.ellipse([28, 28, 36, 36], fill=(80, 80, 80))
    return img


def generate_door_vertical():
    """Door oriented for north-south passage (horizontal wall opening)."""
    img = generate_floor()
    draw = ImageDraw.Draw(img)
    # Door frame (sides)
    draw.rectangle([0, 0, 6, TILE_SIZE - 1], fill=DOOR_FRAME_COLOR)
    draw.rectangle(
        [TILE_SIZE - 7, 0, TILE_SIZE - 1, TILE_SIZE - 1], fill=DOOR_FRAME_COLOR
    )
    # Door plank
    draw.rectangle([7, 8, TILE_SIZE - 8, TILE_SIZE - 9], fill=DOOR_COLOR)
    # Plank lines
    for y in [20, 32, 44]:
        draw.line([(8, y), (TILE_SIZE - 9, y)], fill=CHEST_DARK, width=1)
    # Handle
    draw.ellipse([28, 28, 36, 36], fill=(80, 80, 80))
    return img


def generate_door_horizontal_2(position):
    """Half of a 2-wide horizontal door (passage N-S, frame on N/S walls).
    position: 'left' or 'right'
    """
    img = generate_floor()
    draw = ImageDraw.Draw(img)
    # Frame on top and bottom (wall sides)
    draw.rectangle([0, 0, TILE_SIZE - 1, 6], fill=DOOR_FRAME_COLOR)
    draw.rectangle(
        [0, TILE_SIZE - 7, TILE_SIZE - 1, TILE_SIZE - 1], fill=DOOR_FRAME_COLOR
    )
    if position == "left":
        # Door plank: left edge has frame, right edge extends to tile boundary
        draw.rectangle([8, 7, TILE_SIZE - 1, TILE_SIZE - 8], fill=DOOR_COLOR)
        # Plank grain lines
        for x in [20, 36, 52]:
            draw.line([(x, 8), (x, TILE_SIZE - 9)], fill=CHEST_DARK, width=1)
        # Seam line at right edge
        draw.line(
            [(TILE_SIZE - 1, 7), (TILE_SIZE - 1, TILE_SIZE - 8)],
            fill=CHEST_DARK,
            width=2,
        )
        # Handle near the seam
        draw.ellipse(
            [TILE_SIZE - 14, 28, TILE_SIZE - 6, 36], fill=(80, 80, 80)
        )
    else:
        # Door plank: right edge has frame, left edge extends to tile boundary
        draw.rectangle([0, 7, TILE_SIZE - 9, TILE_SIZE - 8], fill=DOOR_COLOR)
        for x in [12, 28, 44]:
            draw.line([(x, 8), (x, TILE_SIZE - 9)], fill=CHEST_DARK, width=1)
        # Seam line at left edge
        draw.line([(0, 7), (0, TILE_SIZE - 8)], fill=CHEST_DARK, width=2)
        # Handle near the seam
        draw.ellipse([6, 28, 14, 36], fill=(80, 80, 80))
    return img


def generate_door_vertical_2(position):
    """Half of a 2-wide vertical door (passage E-W, frame on E/W walls).
    position: 'top' or 'bottom'
    """
    img = generate_floor()
    draw = ImageDraw.Draw(img)
    # Frame on left and right (wall sides)
    draw.rectangle([0, 0, 6, TILE_SIZE - 1], fill=DOOR_FRAME_COLOR)
    draw.rectangle(
        [TILE_SIZE - 7, 0, TILE_SIZE - 1, TILE_SIZE - 1], fill=DOOR_FRAME_COLOR
    )
    if position == "top":
        # Door plank: top edge has frame, bottom edge extends to tile boundary
        draw.rectangle([7, 8, TILE_SIZE - 8, TILE_SIZE - 1], fill=DOOR_COLOR)
        for y in [20, 36, 52]:
            draw.line([(8, y), (TILE_SIZE - 9, y)], fill=CHEST_DARK, width=1)
        # Seam line at bottom edge
        draw.line(
            [(7, TILE_SIZE - 1), (TILE_SIZE - 8, TILE_SIZE - 1)],
            fill=CHEST_DARK,
            width=2,
        )
        draw.ellipse(
            [28, TILE_SIZE - 14, 36, TILE_SIZE - 6], fill=(80, 80, 80)
        )
    else:
        draw.rectangle([7, 0, TILE_SIZE - 8, TILE_SIZE - 9], fill=DOOR_COLOR)
        for y in [12, 28, 44]:
            draw.line([(8, y), (TILE_SIZE - 9, y)], fill=CHEST_DARK, width=1)
        # Seam line at top edge
        draw.line([(7, 0), (TILE_SIZE - 8, 0)], fill=CHEST_DARK, width=2)
        draw.ellipse([28, 6, 36, 14], fill=(80, 80, 80))
    return img


def generate_door_horizontal_3(position):
    """One third of a 3-wide horizontal door (passage N-S).
    position: 'left', 'center', or 'right'
    """
    img = generate_floor()
    draw = ImageDraw.Draw(img)
    # Frame on top and bottom
    draw.rectangle([0, 0, TILE_SIZE - 1, 6], fill=DOOR_FRAME_COLOR)
    draw.rectangle(
        [0, TILE_SIZE - 7, TILE_SIZE - 1, TILE_SIZE - 1], fill=DOOR_FRAME_COLOR
    )
    if position == "left":
        draw.rectangle([8, 7, TILE_SIZE - 1, TILE_SIZE - 8], fill=DOOR_COLOR)
        for x in [24, 44]:
            draw.line([(x, 8), (x, TILE_SIZE - 9)], fill=CHEST_DARK, width=1)
        draw.line(
            [(TILE_SIZE - 1, 7), (TILE_SIZE - 1, TILE_SIZE - 8)],
            fill=CHEST_DARK,
            width=2,
        )
    elif position == "center":
        draw.rectangle([0, 7, TILE_SIZE - 1, TILE_SIZE - 8], fill=DOOR_COLOR)
        for x in [20, 44]:
            draw.line([(x, 8), (x, TILE_SIZE - 9)], fill=CHEST_DARK, width=1)
        draw.line([(0, 7), (0, TILE_SIZE - 8)], fill=CHEST_DARK, width=2)
        draw.line(
            [(TILE_SIZE - 1, 7), (TILE_SIZE - 1, TILE_SIZE - 8)],
            fill=CHEST_DARK,
            width=2,
        )
        draw.ellipse([28, 28, 36, 36], fill=(80, 80, 80))
    else:
        draw.rectangle([0, 7, TILE_SIZE - 9, TILE_SIZE - 8], fill=DOOR_COLOR)
        for x in [20, 40]:
            draw.line([(x, 8), (x, TILE_SIZE - 9)], fill=CHEST_DARK, width=1)
        draw.line([(0, 7), (0, TILE_SIZE - 8)], fill=CHEST_DARK, width=2)
    return img


def generate_door_vertical_3(position):
    """One third of a 3-wide vertical door (passage E-W).
    position: 'top', 'center', or 'bottom'
    """
    img = generate_floor()
    draw = ImageDraw.Draw(img)
    # Frame on left and right
    draw.rectangle([0, 0, 6, TILE_SIZE - 1], fill=DOOR_FRAME_COLOR)
    draw.rectangle(
        [TILE_SIZE - 7, 0, TILE_SIZE - 1, TILE_SIZE - 1], fill=DOOR_FRAME_COLOR
    )
    if position == "top":
        draw.rectangle([7, 8, TILE_SIZE - 8, TILE_SIZE - 1], fill=DOOR_COLOR)
        for y in [24, 44]:
            draw.line([(8, y), (TILE_SIZE - 9, y)], fill=CHEST_DARK, width=1)
        draw.line(
            [(7, TILE_SIZE - 1), (TILE_SIZE - 8, TILE_SIZE - 1)],
            fill=CHEST_DARK,
            width=2,
        )
    elif position == "center":
        draw.rectangle([7, 0, TILE_SIZE - 8, TILE_SIZE - 1], fill=DOOR_COLOR)
        for y in [20, 44]:
            draw.line([(8, y), (TILE_SIZE - 9, y)], fill=CHEST_DARK, width=1)
        draw.line([(7, 0), (TILE_SIZE - 8, 0)], fill=CHEST_DARK, width=2)
        draw.line(
            [(7, TILE_SIZE - 1), (TILE_SIZE - 8, TILE_SIZE - 1)],
            fill=CHEST_DARK,
            width=2,
        )
        draw.ellipse([28, 28, 36, 36], fill=(80, 80, 80))
    else:
        draw.rectangle([7, 0, TILE_SIZE - 8, TILE_SIZE - 9], fill=DOOR_COLOR)
        for y in [20, 40]:
            draw.line([(8, y), (TILE_SIZE - 9, y)], fill=CHEST_DARK, width=1)
        draw.line([(7, 0), (TILE_SIZE - 8, 0)], fill=CHEST_DARK, width=2)
    return img


def generate_secret_door():
    """Looks like a wall but with a faint crack."""
    img = generate_wall()
    draw = ImageDraw.Draw(img)
    # Subtle crack line
    points = [(30, 5), (32, 15), (28, 25), (33, 35), (30, 45), (32, 58)]
    draw.line(points, fill=SECRET_MARK_COLOR, width=1)
    return img


def generate_water(variant=0):
    img = Image.new("RGB", (TILE_SIZE, TILE_SIZE))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, TILE_SIZE, TILE_SIZE], fill=WATER_COLOR)
    # Wavy highlight lines
    offsets = [0, 3, -2]
    d = offsets[variant % len(offsets)]
    for y in [16 + d, 36 + d, 52 + d]:
        points = []
        for x in range(0, TILE_SIZE, 4):
            wave = 2 if (x // 4 + variant) % 2 == 0 else -2
            points.append((x, y + wave))
        if len(points) > 1:
            draw.line(points, fill=WATER_HIGHLIGHT, width=1)
    return img


def generate_chest():
    img = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Chest body
    draw.rectangle(
        [16, 20, 48, 44], fill=CHEST_COLOR, outline=CHEST_DARK, width=2
    )
    # Chest lid line
    draw.line([(16, 28), (48, 28)], fill=CHEST_DARK, width=2)
    # Lock/clasp
    draw.rectangle(
        [29, 30, 35, 36], fill=(200, 180, 60), outline=(150, 130, 30)
    )
    return img


def generate_bookshelf():
    img = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Shelf frame
    draw.rectangle(
        [12, 14, 52, 50], fill=BOOKSHELF_COLOR, outline=(70, 40, 20), width=2
    )
    # Shelves (horizontal lines)
    draw.line([(13, 26), (51, 26)], fill=(70, 40, 20), width=1)
    draw.line([(13, 38), (51, 38)], fill=(70, 40, 20), width=1)
    # Books on each shelf
    rng = random.Random(123)
    for shelf_y_start, shelf_y_end in [(15, 25), (27, 37), (39, 49)]:
        x = 14
        while x < 50:
            w = rng.randint(2, 5)
            color = rng.choice(BOOKSHELF_BOOK_COLORS)
            draw.rectangle(
                [x, shelf_y_start + 1, min(x + w, 50), shelf_y_end - 1],
                fill=color,
            )
            x += w + 1
    return img


def generate_mimic():
    """Looks like a chest but with a subtle difference (teeth-like edge)."""
    img = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Chest body (same as normal chest)
    draw.rectangle(
        [16, 20, 48, 44], fill=CHEST_COLOR, outline=CHEST_DARK, width=2
    )
    draw.line([(16, 28), (48, 28)], fill=CHEST_DARK, width=2)
    # Teeth along the lid line
    for x in range(18, 48, 4):
        draw.polygon([(x, 28), (x + 2, 24), (x + 4, 28)], fill=(220, 220, 210))
    # Eye
    draw.ellipse([29, 32, 35, 38], fill=(200, 30, 30))
    draw.ellipse([31, 34, 33, 36], fill=(0, 0, 0))
    return img


def generate_ladder_up():
    img = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Hole/opening
    draw.ellipse(
        [12, 12, 52, 52], fill=(40, 35, 30), outline=(60, 50, 40), width=2
    )
    # Ladder rails
    draw.line([(24, 10), (24, 54)], fill=LADDER_COLOR, width=3)
    draw.line([(40, 10), (40, 54)], fill=LADDER_COLOR, width=3)
    # Rungs
    for y in [18, 26, 34, 42, 50]:
        draw.line([(25, y), (39, y)], fill=LADDER_DARK, width=2)
    # Up arrow
    draw.polygon([(32, 6), (26, 14), (38, 14)], fill=(220, 220, 220))
    return img


def generate_column():
    img = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Shadow ring
    draw.ellipse([14, 14, 50, 50], fill=(40, 40, 45))
    # Column base
    draw.ellipse([16, 16, 48, 48], fill=(80, 80, 85))
    # Column body (lighter stone)
    draw.ellipse([19, 19, 45, 45], fill=WALL_LINE_COLOR)
    # Highlight
    draw.ellipse([22, 22, 38, 38], fill=(100, 100, 105))
    return img


def generate_ladder_down():
    img = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Hole/opening
    draw.ellipse(
        [12, 12, 52, 52], fill=(20, 18, 15), outline=(60, 50, 40), width=2
    )
    # Ladder rails
    draw.line([(24, 10), (24, 54)], fill=LADDER_COLOR, width=3)
    draw.line([(40, 10), (40, 54)], fill=LADDER_COLOR, width=3)
    # Rungs
    for y in [18, 26, 34, 42, 50]:
        draw.line([(25, y), (39, y)], fill=LADDER_DARK, width=2)
    # Down arrow
    draw.polygon([(32, 58), (26, 50), (38, 50)], fill=(220, 220, 220))
    return img


def generate_all_tiles():
    """Generate all tile images and save to the tiles directory."""
    os.makedirs(TILES_DIR, exist_ok=True)

    tiles = {
        "wall": generate_wall(),
        "wall_interior": generate_wall_interior(),
        "wall_edge_n": generate_wall_edge("n"),
        "wall_edge_s": generate_wall_edge("s"),
        "wall_edge_e": generate_wall_edge("e"),
        "wall_edge_w": generate_wall_edge("w"),
        "wall_edge_ne": generate_wall_edge("ne"),
        "wall_edge_nw": generate_wall_edge("nw"),
        "wall_edge_se": generate_wall_edge("se"),
        "wall_edge_sw": generate_wall_edge("sw"),
        "wall_edge_ns": generate_wall_edge("ns"),
        "wall_edge_ew": generate_wall_edge("ew"),
        "wall_edge_nsw": generate_wall_edge("nsw"),
        "wall_edge_nse": generate_wall_edge("nse"),
        "wall_edge_new": generate_wall_edge("new"),
        "wall_edge_sew": generate_wall_edge("sew"),
        "wall_edge_nsew": generate_wall_edge("nsew"),
        "cavern_wall": generate_cavern_wall(),
        "cavern_floor_0": generate_cavern_floor(0),
        "cavern_floor_1": generate_cavern_floor(1),
        "cavern_floor_2": generate_cavern_floor(2),
        "cavern_floor_3": generate_cavern_floor(3),
        "cavern_floor_4": generate_cavern_floor(4),
        "cavern_floor_5": generate_cavern_floor(5),
        "floor_0": generate_floor(0),
        "floor_1": generate_floor(1),
        "floor_2": generate_floor(2),
        "corridor_0": generate_corridor(0),
        "corridor_1": generate_corridor(1),
        "door_horizontal": generate_door_horizontal(),
        "door_horizontal_2_left": generate_door_horizontal_2("left"),
        "door_horizontal_2_right": generate_door_horizontal_2("right"),
        "door_horizontal_3_left": generate_door_horizontal_3("left"),
        "door_horizontal_3_center": generate_door_horizontal_3("center"),
        "door_horizontal_3_right": generate_door_horizontal_3("right"),
        "door_vertical": generate_door_vertical(),
        "door_vertical_2_top": generate_door_vertical_2("top"),
        "door_vertical_2_bottom": generate_door_vertical_2("bottom"),
        "door_vertical_3_top": generate_door_vertical_3("top"),
        "door_vertical_3_center": generate_door_vertical_3("center"),
        "door_vertical_3_bottom": generate_door_vertical_3("bottom"),
        "secret_door": generate_secret_door(),
        "water_0": generate_water(0),
        "water_1": generate_water(1),
        "water_2": generate_water(2),
        "chest": generate_chest(),
        "bookshelf": generate_bookshelf(),
        "mimic": generate_mimic(),
        "ladder_up": generate_ladder_up(),
        "ladder_down": generate_ladder_down(),
        "column": generate_column(),
    }

    for name, img in tiles.items():
        path = os.path.join(TILES_DIR, f"{name}.png")
        img.save(path)
        print(f"  Saved {path}")

    print(f"Generated {len(tiles)} tile images in {TILES_DIR}")


if __name__ == "__main__":
    generate_all_tiles()
