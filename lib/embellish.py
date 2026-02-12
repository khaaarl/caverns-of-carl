"""Core embellishment engine for LLM-powered dungeon flavor text.

Provides LLM providers, prompt builders, scope/cost estimation,
and an orchestrator that runs embellishments in parallel threads.
"""

import datetime
import json
import math
import os
import ssl
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from lib.room import CavernousRoom
from lib.utils import COC_ROOT_DIR


def _get_var(var):
    """Get value from a tkinter var or plain value."""
    return var.get() if callable(getattr(var, "get", None)) else var


# ---------------------------------------------------------------------------
# Provider / model definitions
# ---------------------------------------------------------------------------

PROVIDER_MODELS = {
    "Anthropic": [
        {
            "id": "claude-sonnet-4-5-20250929",
            "label": "Claude Sonnet 4.5",
            "input_per_mtok": 3.00,
            "output_per_mtok": 15.00,
        },
        {
            "id": "claude-haiku-4-5-20251001",
            "label": "Claude Haiku 4.5",
            "input_per_mtok": 0.80,
            "output_per_mtok": 4.00,
        },
    ],
}

# Average token counts per element type (input, output).
# Input includes ~200 tokens for few-shot examples + ~100 for atmosphere brief.
_TOKEN_ESTIMATES = {
    "room": (700, 150),
    "corridor": (600, 100),
    "trap": (700, 200),
    "book": (600, 250),
    "atmosphere": (600, 300),
}


def _model_pricing(model_id):
    """Return (input_per_mtok, output_per_mtok) for a model ID."""
    for provider_models in PROVIDER_MODELS.values():
        for m in provider_models:
            if m["id"] == model_id:
                return m["input_per_mtok"], m["output_per_mtok"]
    return 3.00, 15.00


# ---------------------------------------------------------------------------
# Embellishment scope & cost estimation
# ---------------------------------------------------------------------------


class EmbellishmentScope:
    """Which element types to embellish, with cost/time estimation."""

    def __init__(
        self,
        rooms=True,
        corridors=True,
        traps=True,
        books=True,
    ):
        self.rooms = rooms
        self.corridors = corridors
        self.traps = traps
        self.books = books

    def count_elements(self, df):
        """Return dict of element_type -> count for this scope."""
        counts = {}
        if self.rooms:
            counts["room"] = sum(1 for r in df.rooms if not r.is_trivial())
        if self.corridors:
            counts["corridor"] = sum(
                1 for c in df.corridors if c.is_nontrivial(df)
            )
        if self.traps:
            counts["trap"] = len(df.traps)
        if self.books:
            counts["book"] = self._count_books(df)
        return counts

    def _count_books(self, df):
        from lib.tile import BookshelfTile

        count = 0
        for room in df.rooms:
            for x, y in room.tile_coords():
                tile = df.tiles[x][y]
                if isinstance(tile, BookshelfTile) and tile.contents:
                    for line in tile.contents.split("\n"):
                        if line.strip().startswith("Book:"):
                            count += 1
        return count

    def count_api_calls(self, df):
        """Total number of API calls needed (including atmosphere brief)."""
        element_calls = sum(self.count_elements(df).values())
        if element_calls > 0:
            return element_calls + 1  # +1 for atmosphere brief
        return 0

    def estimate_cost_usd(self, df, model_id):
        """Estimated cost in USD."""
        inp_price, out_price = _model_pricing(model_id)
        total = 0.0
        elements = self.count_elements(df)
        for etype, count in elements.items():
            inp_tok, out_tok = _TOKEN_ESTIMATES[etype]
            total += count * (
                inp_tok * inp_price / 1_000_000
                + out_tok * out_price / 1_000_000
            )
        # Add atmosphere brief cost if there are any elements
        if sum(elements.values()) > 0:
            atm_inp, atm_out = _TOKEN_ESTIMATES["atmosphere"]
            total += (
                atm_inp * inp_price / 1_000_000
                + atm_out * out_price / 1_000_000
            )
        return total

    def estimate_time_seconds(self, df):
        """Estimated wall-clock time assuming 5 concurrent workers."""
        element_calls = sum(self.count_elements(df).values())
        if element_calls == 0:
            return 0.0
        # ~3s for sequential atmosphere brief + parallel element calls
        return 3.0 + math.ceil(element_calls / 5) * 2.0


# ---------------------------------------------------------------------------
# Embellishment result
# ---------------------------------------------------------------------------


class EmbellishmentResult:
    """Holds the generated flavor text for one dungeon element."""

    def __init__(
        self,
        element_type,
        element_id,
        element_name,
        flavor_text,
        system_prompt,
        user_prompt,
        error=None,
        elapsed_seconds=0.0,
    ):
        self.element_type = element_type
        self.element_id = element_id
        self.element_name = element_name
        self.flavor_text = flavor_text  # None on error
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.error = error  # str on failure
        self.elapsed_seconds = elapsed_seconds


# ---------------------------------------------------------------------------
# Tone mappings
# ---------------------------------------------------------------------------

TONE_MAP = {
    "Classic D&D": (
        "Evocative high fantasy in the style of classic D&D adventure "
        "modules. Mysterious, adventurous, with a sense of wonder and "
        "danger."
    ),
    "Grimdark": (
        "Dark, oppressive, and bleak. Emphasize horror, rot, and despair."
    ),
    "Whimsical": (
        "Light-hearted, playful, and slightly absurd. Charm and humor "
        "despite danger."
    ),
    "Lovecraftian": (
        "Cosmic horror. Geometry feels wrong, reality bends, ancient "
        "things stir."
    ),
}


def _tone_description(tone):
    """Return the full tone description string for prompt inclusion."""
    return TONE_MAP.get(tone, tone)


# ---------------------------------------------------------------------------
# Few-shot examples (per tone)
# ---------------------------------------------------------------------------

_FEW_SHOT_EXAMPLES = {
    "Classic D&D": [
        {
            "user": (
                "Write atmospheric read-aloud text for this dungeon room.\n\n"
                "Room: Room 5\n"
                "Type: rectangular\n"
                "Size: roughly 35 ft x 25 ft\n"
                "Biome: standard dungeon\n"
                "Light level: dim\n"
                "Contents: monsters: 2 skeletons\n"
                "Exits: east: wooden door; south: open corridor"
            ),
            "assistant": (
                "Guttering torchlight barely reaches the far walls of "
                "this chamber, where dust motes drift like lazy fireflies. "
                "Two armored skeletons stand motionless near an overturned "
                "table, their empty eye sockets fixed on the doorway. "
                "The air carries a dry, papery scent — old parchment "
                "and older bone."
            ),
        },
        {
            "user": (
                "Write atmospheric read-aloud text for this dungeon "
                "corridor.\n\n"
                "Corridor: D\n"
                "Width: 10 ft\n"
                "Length: ~40 ft\n"
                "Style: dungeon\n"
                "Light level: dark"
            ),
            "assistant": (
                "Darkness swallows the corridor ahead, broken only by "
                "the feeble reach of your light. The flagstones underfoot "
                "are slick with condensation, and somewhere ahead water "
                "drips in a slow, echoing rhythm."
            ),
        },
    ],
    "Grimdark": [
        {
            "user": (
                "Write atmospheric read-aloud text for this dungeon room.\n\n"
                "Room: Room 2\n"
                "Type: cavernous/irregular\n"
                "Size: roughly 45 ft x 35 ft\n"
                "Biome: standard dungeon\n"
                "Light level: dark\n"
                "Contents: a downward ladder; a treasure chest\n"
                "Exits: west: iron door"
            ),
            "assistant": (
                "The cavern walls weep with dark moisture that glistens "
                "like old blood. A rusted iron chest squats in the center, "
                "its lock fused with corrosion, and beyond it a ladder "
                "descends into a shaft of absolute blackness. "
                "The stench of rot rises from below, thick enough to taste."
            ),
        },
        {
            "user": (
                "Write atmospheric read-aloud text for this dungeon "
                "corridor.\n\n"
                "Corridor: B\n"
                "Width: 5 ft\n"
                "Length: ~30 ft\n"
                "Style: cavern\n"
                "Light level: dim"
            ),
            "assistant": (
                "The passage tightens like a throat, rough stone pressing "
                "in from both sides. Something has scratched long, "
                "desperate grooves into the rock at shoulder height. "
                "A faint, sour draft carries the promise of worse "
                "things ahead."
            ),
        },
    ],
    "Whimsical": [
        {
            "user": (
                "Write atmospheric read-aloud text for this dungeon room.\n\n"
                "Room: Room 1\n"
                "Type: rectangular\n"
                "Size: roughly 25 ft x 25 ft\n"
                "Biome: standard dungeon\n"
                "Light level: bright\n"
                "Contents: 2 bookshelves\n"
                "Exits: north: wooden door; east: open corridor"
            ),
            "assistant": (
                "Cheerful bioluminescent moss coats the ceiling in "
                "swirling patterns, casting the room in a pleasant "
                "blue-green glow. Two bookshelves lean against each other "
                "like old friends sharing secrets, their contents a "
                "jumble of serious-looking tomes and what appear to be "
                "illustrated cookbooks."
            ),
        },
        {
            "user": (
                "Write atmospheric read-aloud text for this dungeon "
                "corridor.\n\n"
                "Corridor: A\n"
                "Width: 10 ft\n"
                "Length: ~25 ft\n"
                "Style: dungeon\n"
                "Light level: bright"
            ),
            "assistant": (
                "Someone has laid a cheerful red carpet down the center "
                "of this hallway — though it's seen better days and "
                "currently hosts a family of beetles having what looks "
                "like a very organized picnic."
            ),
        },
    ],
    "Lovecraftian": [
        {
            "user": (
                "Write atmospheric read-aloud text for this dungeon room.\n\n"
                "Room: Room 4\n"
                "Type: cavernous/irregular\n"
                "Size: roughly 55 ft x 45 ft\n"
                "Biome: standard dungeon\n"
                "Light level: dark\n"
                "Contents: monsters: 1 gibbering mouther\n"
                "Exits: south: open cavern passage"
            ),
            "assistant": (
                "The chamber's dimensions resist comprehension — walls "
                "that should be parallel somehow converge at angles your "
                "mind refuses to calculate. A shapeless mass of mouths "
                "and eyes quivers in the far corner, babbling in a "
                "language that predates spoken word. You are certain "
                "the ceiling is watching."
            ),
        },
        {
            "user": (
                "Write atmospheric read-aloud text for this dungeon "
                "corridor.\n\n"
                "Corridor: C\n"
                "Width: 10 ft\n"
                "Length: ~50 ft\n"
                "Style: dungeon\n"
                "Light level: dim"
            ),
            "assistant": (
                "The corridor stretches ahead, but its length seems "
                "to shift when you're not looking directly at it. "
                "The stone walls bear faint spiral carvings that "
                "pull your gaze inward, deeper, toward a center that "
                "doesn't exist."
            ),
        },
    ],
}


def _get_few_shot_examples(tone):
    """Return few-shot examples for a tone, falling back to Classic D&D."""
    return _FEW_SHOT_EXAMPLES.get(tone, _FEW_SHOT_EXAMPLES["Classic D&D"])


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
You are a Dungeon Master writing atmospheric descriptions for a D&D 5e dungeon.
Your tone is: {tone_description}.

Rules:
- Write in second person ("You see...", "The air smells of...")
- Keep descriptions to 2-4 sentences
- Focus on sensory details: sight, sound, smell, touch
- Do not invent mechanical elements (no monsters, traps, or treasure not already present)
- Do not reference specific game mechanics or dice rolls"""


def _system_prompt(tone):
    prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        tone_description=_tone_description(tone)
    )
    examples = _get_few_shot_examples(tone)
    prompt += "\n\nHere are examples of the style and length expected:"
    for i, ex in enumerate(examples, 1):
        prompt += f"\n\n--- Example {i} ---"
        prompt += f"\nUser: {ex['user']}"
        prompt += f"\nAssistant: {ex['assistant']}"
    return prompt


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _direction_from_point(room, x, y):
    """Return a cardinal direction from a room's center to a point.

    Uses wall proximity: whichever room wall the point is closest to
    determines the direction. This is more reliable than a simple
    center-to-point vector for non-square rooms.
    """
    dists = {
        "north": abs(y - (room.y + room.rh)),
        "south": abs(y - (room.y - room.rh)),
        "east": abs(x - (room.x + room.rw)),
        "west": abs(x - (room.x - room.rw)),
    }
    return min(dists, key=lambda d: dists[d])


def _format_monsters(monsters):
    """Format a monster list with counts, e.g. '3 skeletons, 1 ogre'."""
    from collections import Counter

    counts = Counter(m.name for m in monsters)
    parts = []
    for name, count in counts.items():
        if count == 1:
            parts.append(name)
        else:
            parts.append(f"{count} {name}s")
    return ", ".join(parts)


def build_room_prompt(df, room, tone):
    """Build (system_prompt, user_prompt) for a room."""
    from lib.tile import BookshelfTile, ChestTile, MimicTile

    room_type = "rectangular"
    if isinstance(room, CavernousRoom):
        room_type = "cavernous/irregular"
    width_ft = (room.rw * 2 + 1) * 5
    height_ft = (room.rh * 2 + 1) * 5

    # Collect room contents (excluding traps — handled separately)
    contents = []
    if room.has_up_ladder:
        contents.append("an upward ladder")
    if room.has_down_ladder:
        contents.append("a downward ladder")
    if room.encounter:
        formatted = _format_monsters(room.encounter.monsters)
        if formatted:
            contents.append(f"monsters: {formatted}")

    # Scan tiles for chests and bookshelves
    n_chests = 0
    n_bookshelves = 0
    for x, y in room.tile_coords():
        tile = df.tiles[x][y]
        if isinstance(tile, MimicTile):
            # Mimics look like chests — count as chest
            n_chests += 1
        elif isinstance(tile, BookshelfTile):
            n_bookshelves += 1
        elif isinstance(tile, ChestTile):
            n_chests += 1
    if n_chests == 1:
        contents.append("a treasure chest")
    elif n_chests > 1:
        contents.append(f"{n_chests} treasure chests")
    if n_bookshelves == 1:
        contents.append("a bookshelf")
    elif n_bookshelves > 1:
        contents.append(f"{n_bookshelves} bookshelves")

    # Describe physical exits and collect secret doors separately.
    # Uses the same corridorix→door mapping pattern as Room.description().
    exits = []
    secret_exits = []
    corridorix_doors = {k: None for k in room.corridorixs}
    for doorix in room.doorixs:
        door = df.doors[doorix]
        corridorix_doors[door.corridorix] = door
    for corridorix, door in corridorix_doors.items():
        corridor = df.corridors[corridorix]
        if door and door.is_secret:
            direction = _direction_from_point(room, door.x, door.y)
            secret_exits.append(
                f"{direction} wall: {door.nickname().lower()}"
                f" (DC {door.detection_dc})"
            )
        elif door:
            direction = _direction_from_point(room, door.x, door.y)
            exits.append(f"{direction}: {door.nickname().lower()}")
        else:
            # Open passage — use corridor endpoint nearest this room
            direction = _passage_direction(room, corridor)
            style = corridor.tile_style()
            if style == "cavern":
                exits.append(f"{direction}: open cavern passage")
            else:
                exits.append(f"{direction}: open corridor")

    biome = room.biome_name or "standard dungeon"

    # Check for traps and secret doors
    has_trap = bool(room.trapixs)
    has_secrets = has_trap or bool(secret_exits)

    system = _system_prompt(tone)
    if has_secrets:
        system += "\n"
    if has_trap:
        system += (
            "\nThis room contains a hidden trap. Your main description "
            "must NOT mention the trap directly — the players have not "
            "found it yet. You may weave in one subtle sensory hint "
            "(an odd smell, a faint click, a too-clean patch of floor) "
            "but nothing obvious.\n"
            "After the main description, add a separate section on a new "
            "line starting with TRAP DETECTED: that gives 1-2 sentences "
            "a DM reads aloud only when a player succeeds on a "
            "Perception/Investigation check. This section should "
            "describe what the player notices about the trap."
        )
    if secret_exits:
        system += (
            "\nThis room has one or more secret doors. Do NOT mention "
            "them in the main description — the wall should appear "
            "solid. You may include a very subtle hint (a faint draft, "
            "slightly mismatched stonework) but nothing obvious.\n"
            "After the main description (and after TRAP DETECTED if "
            "present), add a section on a new line starting with "
            "SECRET DOOR: for each secret exit, giving 1-2 sentences "
            "the DM reads when a player finds it."
        )

    user_prompt = (
        f"Write atmospheric read-aloud text for this dungeon room.\n\n"
        f"Room: {room.name()}\n"
        f"Type: {room_type}\n"
        f"Size: roughly {width_ft} ft x {height_ft} ft\n"
        f"Biome: {biome}\n"
        f"Light level: {room.light_level}\n"
    )
    if contents:
        user_prompt += f"Contents: {'; '.join(contents)}\n"
    if exits:
        user_prompt += f"Exits: {'; '.join(exits)}\n"
    if has_trap:
        trap = df.traps[list(room.trapixs)[0]]
        user_prompt += f"Hidden trap: {trap.trigger} — {trap.effect}\n"
    if secret_exits:
        user_prompt += f"Secret exits: {'; '.join(secret_exits)}\n"

    user_prompt += (
        "\nDo not describe the party entering or opening a door — "
        "describe the room as it appears once the party can see inside."
    )

    return system, user_prompt


def _passage_direction(room, corridor):
    """Determine the exit direction for an open (doorless) passage.

    Uses the vector from this room's center toward the other room's
    endpoint to find the general direction the passage leads.
    """
    if room.ix == corridor.room1ix:
        ex, ey = corridor.x2, corridor.y2
    else:
        ex, ey = corridor.x1, corridor.y1
    dx = ex - room.x
    dy = ey - room.y
    if abs(dx) >= abs(dy):
        return "east" if dx > 0 else "west"
    return "north" if dy > 0 else "south"


# ---------------------------------------------------------------------------
# Atmosphere brief (two-pass approach)
# ---------------------------------------------------------------------------


def _gather_biome_stats(df):
    """Gather per-biome statistics from the dungeon floor.

    Returns dict mapping biome_name (or None for default) to a stats dict:
    {
        "room_count": int,
        "room_types": {"rectangular": n, "cavernous": n},
        "corridor_count": int,
        "corridor_styles": {"dungeon": n, "cavern": n},
        "light_counts": {"bright": n, "dim": n, "dark": n},
        "monster_names": set[str],
        "trap_count": int,
        "structure_style": str,
        "cavern_style": str,
    }
    """
    # Discover biome names from rooms and corridors
    biome_names = set()
    for room in df.rooms:
        if not room.is_trivial():
            biome_names.add(room.biome_name)
    for corridor in df.corridors:
        if corridor.is_nontrivial(df):
            biome_names.add(corridor.biome_name)

    stats = {}
    for bname in biome_names:
        biome_config = df.config.get_biome(bname)
        s = {
            "room_count": 0,
            "room_types": {"rectangular": 0, "cavernous": 0},
            "corridor_count": 0,
            "corridor_styles": {"dungeon": 0, "cavern": 0},
            "light_counts": {"bright": 0, "dim": 0, "dark": 0},
            "monster_names": set(),
            "trap_count": 0,
            "structure_style": _get_var(biome_config.structure_style),
            "cavern_style": _get_var(biome_config.cavern_style),
        }
        stats[bname] = s

    for room in df.rooms:
        if room.is_trivial():
            continue
        s = stats.get(room.biome_name)
        if s is None:
            continue
        s["room_count"] += 1
        if isinstance(room, CavernousRoom):
            s["room_types"]["cavernous"] += 1
        else:
            s["room_types"]["rectangular"] += 1
        ll = room.light_level
        if ll in s["light_counts"]:
            s["light_counts"][ll] += 1
        if room.encounter:
            for m in room.encounter.monsters:
                s["monster_names"].add(m.name)
        s["trap_count"] += len(room.trapixs)

    for corridor in df.corridors:
        if not corridor.is_nontrivial(df):
            continue
        s = stats.get(corridor.biome_name)
        if s is None:
            continue
        s["corridor_count"] += 1
        style = corridor.tile_style()
        if style in s["corridor_styles"]:
            s["corridor_styles"][style] += 1

    return stats


def build_atmosphere_prompt(df, tone):
    """Build (system_prompt, user_prompt) for a dungeon atmosphere brief.

    The atmosphere brief gives the LLM shared context about the dungeon's
    overall feel, used to inform all subsequent element descriptions.
    """
    biome_stats = _gather_biome_stats(df)
    width_ft = _get_var(df.config.width) * 5
    height_ft = _get_var(df.config.height) * 5
    has_rivers = bool(df.rivers)
    multi_biome = len(biome_stats) > 1

    system = (
        "You are a Dungeon Master preparing an atmosphere brief for a "
        "D&D 5e dungeon floor. Your tone is: "
        f"{_tone_description(tone)}.\n\n"
        "Write a concise atmosphere brief (150-300 words) that captures "
        "the overall mood, sensory environment, and character of this "
        "dungeon floor. This brief will be used as shared context for "
        "writing individual room and corridor descriptions.\n\n"
        "Focus on:\n"
        "- Overall mood and atmosphere\n"
        "- Recurring sensory details (sounds, smells, textures)\n"
        "- Architectural character and state of repair\n"
        "- What makes this place feel distinct\n"
    )
    if multi_biome:
        system += (
            "\nThis dungeon has multiple distinct regions (biomes). "
            "Describe each region and how they contrast. "
            "Format with [Biome Name] section headers for each region."
        )

    user = f"Dungeon floor: {width_ft} ft x {height_ft} ft\n"
    if has_rivers:
        user += "Features: underground river/waterway present\n"
    user += "\n"

    for bname, s in biome_stats.items():
        label = bname or "Main Dungeon"
        if multi_biome:
            user += f"--- {label} ---\n"
        user += f"Architecture: {s['structure_style']}"
        if s["room_types"]["cavernous"] > 0:
            user += f", with {s['cavern_style']} areas"
        user += "\n"
        user += (
            f"Rooms: {s['room_count']} "
            f"({s['room_types']['rectangular']} rectangular, "
            f"{s['room_types']['cavernous']} cavernous)\n"
        )
        user += f"Corridors: {s['corridor_count']}\n"
        lc = s["light_counts"]
        light_parts = []
        for level in ("bright", "dim", "dark"):
            if lc[level] > 0:
                light_parts.append(f"{lc[level]} {level}")
        if light_parts:
            user += f"Lighting: {', '.join(light_parts)}\n"
        if s["monster_names"]:
            user += f"Inhabitants: {', '.join(sorted(s['monster_names']))}\n"
        if s["trap_count"]:
            user += f"Traps: {s['trap_count']}\n"
        user += "\n"

    return system.strip(), user.strip()


def _extract_biome_section(brief, biome_name):
    """Extract the section for a specific biome from an atmosphere brief.

    Looks for [Biome Name] markers. Returns the full brief if biome_name
    is None, the marker is not found, or there's only one section.
    """
    if biome_name is None or not brief:
        return brief

    marker = f"[{biome_name}]"
    pos = brief.find(marker)
    if pos == -1:
        return brief

    # Find the start of content after the marker
    start = pos + len(marker)
    # Find the next section marker
    next_bracket = brief.find("\n[", start)
    if next_bracket == -1:
        section = brief[start:]
    else:
        section = brief[start:next_bracket]

    return section.strip() or brief


def _inject_atmosphere(user_prompt, atmosphere_brief, biome_name):
    """Prepend atmosphere context to a user prompt.

    If atmosphere_brief is None, returns user_prompt unchanged.
    Extracts the relevant biome section from multi-biome briefs.
    """
    if atmosphere_brief is None:
        return user_prompt
    section = _extract_biome_section(atmosphere_brief, biome_name)
    return f"Dungeon atmosphere context:\n{section}\n\n{user_prompt}"


def build_corridor_prompt(df, corridor, tone):
    """Build (system_prompt, user_prompt) for a corridor."""
    door_types = []
    for doorix in corridor.doorixs:
        door = df.doors[doorix]
        if not door.is_secret:
            door_types.append(door.nickname().lower())

    length_ft = corridor.length(df) * 5
    width_ft = corridor.width * 5
    style = corridor.tile_style()

    user_prompt = (
        f"Write atmospheric read-aloud text for this dungeon corridor.\n\n"
        f"Corridor: {corridor.name}\n"
        f"Width: {width_ft} ft\n"
        f"Length: ~{length_ft:.0f} ft\n"
        f"Style: {style}\n"
        f"Light level: {corridor.light_level}\n"
    )
    if door_types:
        user_prompt += f"Doors: {', '.join(door_types)}\n"

    user_prompt += (
        "\nDo not describe the party entering or opening a door — "
        "describe the corridor as it appears once the party can see inside."
    )

    return _system_prompt(tone), user_prompt


def build_trap_prompt(df, trap, tone):
    """Build (system_prompt, user_prompt) for a trap with tiered descriptions."""
    system = _system_prompt(tone) + (
        "\n\nFor traps, write three tiers of description based on "
        "how the party discovers it. Format your response exactly as:\n"
        "PASSIVE: [one sentence of vague unease]\n"
        "PERCEPTION: [two sentences, trap is spotted]\n"
        "INVESTIGATION: [two sentences, full understanding]"
    )

    user_prompt = (
        f"Write tiered read-aloud descriptions for this trap.\n\n"
        f"Trigger: {trap.trigger}\n"
        f"Effect: {trap.effect}\n"
        f"Notice DC: {trap.notice_dc}\n"
        f"Disarm DC: {trap.disarm_dc}\n"
    )

    return system, user_prompt


def build_book_prompt(df, tone):
    """Build (system_prompt, user_prompt) for generating a bespoke book."""
    system = _system_prompt(tone) + (
        "\n\nFor books, generate a complete book entry. "
        "Format your response exactly as:\n"
        "TITLE: [book title]\n"
        "AUTHOR: [author name]\n"
        "DESCRIPTION: [one sentence physical description]\n"
        "SYNOPSIS: [2-3 sentence plot/content summary]\n"
        "EXCERPT: [1-2 sentence quote from the book]"
    )

    user_prompt = (
        "Generate a book that might be found in a D&D dungeon. "
        "It should feel like it belongs in this world — it could be "
        "a tome of lore, a journal, a spellbook's notes, a religious "
        "text, a bestiary, or something stranger."
    )

    return system, user_prompt


# ---------------------------------------------------------------------------
# LLM Providers
# ---------------------------------------------------------------------------


class LLMProvider:
    """Base class for LLM API providers."""

    def generate(self, system_prompt, user_prompt):
        raise NotImplementedError


def _extract_api_error_message(status_code, body):
    """Parse a human-readable message from an Anthropic API error response."""
    try:
        data = json.loads(body)
        msg = data.get("error", {}).get("message", "")
        if msg:
            return msg
    except (json.JSONDecodeError, AttributeError):
        pass
    # Fallback to status code descriptions
    code_messages = {
        401: "Invalid API key. Check your key and try again.",
        403: "Access denied. Your API key may lack permissions.",
        429: "Rate limited. Too many requests — try again shortly.",
        500: "Anthropic server error. Try again later.",
        529: "Anthropic API is overloaded. Try again later.",
    }
    return code_messages.get(status_code, f"API error (HTTP {status_code})")


class AnthropicProvider(LLMProvider):
    """Calls the Anthropic Messages API via urllib (no extra dependencies)."""

    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key, model="claude-sonnet-4-5-20250929"):
        self.api_key = api_key
        self.model = model

    def generate(self, system_prompt, user_prompt):
        """Send a request to the Anthropic API and return the text response."""
        body = {
            "model": self.model,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        data = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        req = urllib.request.Request(
            self.API_URL, data=data, headers=headers, method="POST"
        )
        ctx = ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            # Extract text from the response
            for block in result.get("content", []):
                if block.get("type") == "text":
                    return block["text"]
            return ""
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            message = _extract_api_error_message(e.code, error_body)
            raise RuntimeError(message) from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error: {e.reason}") from e


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def _collect_books(df):
    """Yield (room, x, y, tile, book_line_index, book_title) for each book."""
    from lib.tile import BookshelfTile

    for room in df.rooms:
        for x, y in room.tile_coords():
            tile = df.tiles[x][y]
            if not isinstance(tile, BookshelfTile) or not tile.contents:
                continue
            for i, line in enumerate(tile.contents.split("\n")):
                stripped = line.strip()
                if stripped.startswith("Book:"):
                    title = stripped[len("Book:") :].strip()
                    yield (room, x, y, tile, i, title)


def embellish_dungeon(
    df, scope, provider, tone, progress_callback=None, cancel_event=None
):
    """Run embellishment tasks in two passes and return results.

    Pass 1: Generate an atmosphere brief (sequential).
    Pass 2: Generate individual element descriptions (parallel),
            with the atmosphere brief injected into each prompt.

    Args:
        df: DungeonFloor to embellish.
        scope: EmbellishmentScope controlling which elements to process.
        provider: LLMProvider instance.
        tone: Tone name or custom string.
        progress_callback: Called as
            progress_callback(completed, total, result).
        cancel_event: threading.Event; if set, stops submitting new tasks.

    Returns:
        (results, fatal_error) tuple.  ``fatal_error`` is a string if
        processing was aborted early, otherwise None.
    """
    # Build element tasks (with biome_name for atmosphere injection)
    tasks = []

    if scope.rooms:
        for room in df.rooms:
            if room.is_trivial():
                continue
            sys_p, usr_p = build_room_prompt(df, room, tone)
            tasks.append(
                ("room", room.ix, room.name(), sys_p, usr_p, room.biome_name)
            )

    if scope.corridors:
        for corridor in df.corridors:
            if not corridor.is_nontrivial(df):
                continue
            sys_p, usr_p = build_corridor_prompt(df, corridor, tone)
            tasks.append(
                (
                    "corridor",
                    corridor.ix,
                    f"Corridor {corridor.name}",
                    sys_p,
                    usr_p,
                    corridor.biome_name,
                )
            )

    if scope.traps:
        for i, trap in enumerate(df.traps):
            sys_p, usr_p = build_trap_prompt(df, trap, tone)
            tasks.append(("trap", i, f"Trap {i + 1}", sys_p, usr_p, None))

    if scope.books:
        for room, x, y, tile, line_ix, title in _collect_books(df):
            book_id = (x, y, line_ix)
            sys_p, usr_p = build_book_prompt(df, tone)
            tasks.append(
                ("book", book_id, f"Book: {title}", sys_p, usr_p, None)
            )

    if not tasks:
        return [], None

    total = len(tasks) + 1  # +1 for atmosphere brief
    results = []
    completed = [0]
    fatal_error = [None]

    # --- Pass 1: Atmosphere brief (sequential) ---
    atmosphere_brief = None
    atm_sys, atm_usr = build_atmosphere_prompt(df, tone)
    t0 = time.monotonic()
    atm_error = None
    try:
        if cancel_event and cancel_event.is_set():
            return [], None
        atmosphere_brief = provider.generate(atm_sys, atm_usr)
    except Exception as e:
        atm_error = str(e)
        atmosphere_brief = None
    atm_elapsed = time.monotonic() - t0

    atm_result = EmbellishmentResult(
        "atmosphere",
        0,
        "Atmosphere Brief",
        atmosphere_brief,
        atm_sys,
        atm_usr,
        atm_error,
        atm_elapsed,
    )
    results.append(atm_result)
    completed[0] = 1
    if progress_callback:
        progress_callback(1, total, atm_result)

    # If atmosphere failed, continue without it (graceful degradation)
    if cancel_event and cancel_event.is_set():
        return results, fatal_error[0]

    # --- Pass 2: Element descriptions (parallel) ---
    def _run_one(task):
        etype, eid, name, sys_p, usr_p, biome_name = task
        # Inject atmosphere context into user prompt
        usr_p = _inject_atmosphere(usr_p, atmosphere_brief, biome_name)
        error_msg = None
        t0 = time.monotonic()
        try:
            text = provider.generate(sys_p, usr_p)
        except Exception as e:
            error_msg = str(e)
            text = None
            if cancel_event:
                cancel_event.set()
            if not fatal_error[0]:
                fatal_error[0] = error_msg
        elapsed = time.monotonic() - t0
        result = EmbellishmentResult(
            etype, eid, name, text, sys_p, usr_p, error_msg, elapsed
        )
        completed[0] += 1
        if progress_callback:
            progress_callback(completed[0], total, result)
        return result

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for task in tasks:
            if cancel_event and cancel_event.is_set():
                break
            futures.append(executor.submit(_run_one, task))
        for future in futures:
            if cancel_event and cancel_event.is_set():
                break
            result = future.result()
            results.append(result)

    return results, fatal_error[0]


def write_log_file(results):
    """Write results to a JSONL log file. Returns the file path."""
    log_dir = os.path.join(COC_ROOT_DIR, "output", "embellish_logs")
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    path = os.path.join(log_dir, f"{timestamp}.jsonl")
    with open(path, "w") as f:
        for r in results:
            f.write(
                json.dumps(
                    {
                        "element_type": r.element_type,
                        "element_name": r.element_name,
                        "system_prompt": r.system_prompt,
                        "user_prompt": r.user_prompt,
                        "response": r.flavor_text,
                        "error": r.error,
                        "elapsed_seconds": round(r.elapsed_seconds, 3),
                    }
                )
                + "\n"
            )
    return path


def apply_embellishments(df, results):
    """Apply embellishment results to the dungeon floor objects."""
    from lib.tile import BookshelfTile

    for r in results:
        if r.flavor_text is None:
            continue
        if r.element_type == "room":
            room = df.rooms[r.element_id]
            room.flavor_text = r.flavor_text

        elif r.element_type == "corridor":
            corridor = df.corridors[r.element_id]
            corridor.flavor_text = r.flavor_text

        elif r.element_type == "trap":
            trap = df.traps[r.element_id]
            trap.flavor_text = r.flavor_text

        elif r.element_type == "book":
            x, y, line_ix = r.element_id
            tile = df.tiles[x][y]
            if not isinstance(tile, BookshelfTile):
                continue
            # Parse the structured book response and update the
            # book's contents line
            parsed = _parse_book_response(r.flavor_text)
            if parsed:
                lines = tile.contents.split("\n")
                if line_ix < len(lines):
                    old_title = lines[line_ix].strip()
                    if old_title.startswith("Book:"):
                        old_title = old_title[len("Book:") :].strip()
                    new_title = parsed.get("TITLE", old_title)
                    author = parsed.get("AUTHOR", "")
                    desc = parsed.get("DESCRIPTION", "")
                    synopsis = parsed.get("SYNOPSIS", "")
                    excerpt = parsed.get("EXCERPT", "")
                    parts = [f"Book: {new_title}"]
                    if author:
                        parts.append(f"  by {author}")
                    if desc:
                        parts.append(f"  {desc}")
                    if synopsis:
                        parts.append(f"  {synopsis}")
                    if excerpt:
                        parts.append(f'  "{excerpt}"')
                    lines[line_ix] = "\n".join(parts)
                    tile.contents = "\n".join(lines)


def _parse_book_response(text):
    """Parse structured TITLE/AUTHOR/etc. lines from LLM response."""
    result = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        for key in ("TITLE", "AUTHOR", "DESCRIPTION", "SYNOPSIS", "EXCERPT"):
            if line.upper().startswith(key + ":"):
                result[key] = line[len(key) + 1 :].strip()
                break
    return result if result else None
