from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk
from typing import Any


class Tooltip:
    """Hover tooltip for tkinter widgets."""

    DELAY_MS = 500

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self._after_id = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._cancel)

    def _schedule(self, event=None):
        self._cancel()
        self._after_id = self.widget.after(self.DELAY_MS, self._show)

    def _cancel(self, event=None):
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None
        self._hide()

    def _show(self):
        if self.tipwindow:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 2
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tw,
            text=self.text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            wraplength=300,
        ).pack(ipadx=4, ipady=2)

    def _hide(self):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


class DungeonConfig:
    """All dungeon generation parameters. Also serves as biome sub-configs.

    Each parameter is backed by a tkinter var for the GUI. Biomes are
    child DungeonConfig instances with biome-specific overrides.
    """

    TAB_GROUPS = ["Terrain", "Combat", "Features"]

    # Explicit row layouts per tab group. Each entry is a tuple of key
    # names: 2-tuple = side by side, 1-tuple = single column (left half
    # for short entries, full width for long entries). Keys present in
    # the layout but absent from a config's ui_ops become spacer rows.
    TAB_GROUP_LAYOUTS: dict[str, list[tuple[str, ...]]] = {
        "Terrain": [
            ("min_room_radius", "use_maze_layout"),
            ("cavernous_room_percent", "num_erosion_steps"),
            ("structure_style",),
            ("cavern_style",),
            ("room_bright_ratio",),
            ("room_dim_ratio",),
            ("room_dark_ratio",),
            ("corridor_width_1_ratio",),
            ("corridor_width_2_ratio",),
            ("corridor_width_3_ratio",),
            ("corridor_off_center_percent", "corridor_multi_turn_percent"),
            ("num_up_ladders", "num_down_ladders"),
            ("column_percent",),
            # Biome-specific (spacer rows in Overall)
            ("biome_northness", "biome_southness"),
            ("biome_westness", "biome_eastness"),
            ("min_num_rivers", "max_num_rivers"),
        ],
        "Combat": [
            ("target_character_level", "num_player_characters"),
            ("room_encounter_percent",),
            ("encounter_xp_low_percent", "encounter_xp_high_percent"),
            ("monster_filter",),
            ("num_treasures", "num_mimics"),
            ("num_bookshelves",),
            ("trap_damage_low_multiplier", "trap_damage_high_multiplier"),
            ("room_trap_percent", "corridor_trap_percent"),
            ("door_trap_percent", "chest_trap_percent"),
            ("door_lock_percent", "door_secret_percent"),
        ],
        "Features": [
            ("blacksmith_percent",),
            ("kryxix_altar_percent",),
            ("ssarthaxx_altar_percent",),
        ],
    }

    TOOLTIPS: dict[str, str] = {
        # -- Global --
        "width": "Map width in tiles",
        "height": "Map height in tiles",
        "num_rooms": "Number of rooms to place on the map",
        "num_room_embiggenings": "Number of times to randomly enlarge an existing room",
        "num_room_wiggles": "Number of times to randomly shift a room's position",
        "prefer_full_connection": "Try to connect all rooms via corridors (may retry on failure)",
        "min_corridors_per_room": "Minimum average corridors per room (e.g. 1.1 = at least 1 per room plus extras)",
        "use_pathfinding_fallback": "Use A* pathfinding when straight-line corridors fail",
        "num_rivers": "Number of rivers to generate (global override; use per-biome min/max for biome control)",
        "min_ladder_distance": "Minimum room distance between up and down ladders",
        "num_misc_NPCs": "Dice expression for number of misc NPCs (e.g. 1d6-1)",
        "tts_fog_of_war": "Enable fog of war zones in Tabletop Simulator export",
        "tts_hidden_zones": "Create hidden zones around rooms in TTS export",
        "tts_notecards": "Create notecards with room info in TTS export",
        "save_map_image": "Save 2D map image (PNG) when exporting",
        # -- Terrain --
        "biome_northness": "Weight for this biome to appear in the north of the map",
        "biome_southness": "Weight for this biome to appear in the south of the map",
        "biome_westness": "Weight for this biome to appear in the west of the map",
        "biome_eastness": "Weight for this biome to appear in the east of the map",
        "min_room_radius": "Minimum room radius in tiles (before embiggen)",
        "use_maze_layout": "Use maze-style room layout (small connected junctions instead of open rooms)",
        "cavernous_room_percent": "Percent chance each room is cavernous (irregular shape via erosion)",
        "num_erosion_steps": "Number of erosion passes for cavernous rooms (higher = more irregular)",
        "structure_style": "Visual style for structured (non-cavernous) rooms and corridors",
        "cavern_style": "Visual style for cavernous rooms",
        "room_bright_ratio": "Relative weight for rooms to have bright lighting",
        "room_dim_ratio": "Relative weight for rooms to have dim lighting",
        "room_dark_ratio": "Relative weight for rooms to have no lighting (dark)",
        "corridor_width_1_ratio": "Relative weight for corridors to be 1 tile wide",
        "corridor_width_2_ratio": "Relative weight for corridors to be 2 tiles wide",
        "corridor_width_3_ratio": "Relative weight for corridors to be 3 tiles wide",
        "corridor_off_center_percent": "Percent chance a corridor exits off-center from the room wall",
        "corridor_multi_turn_percent": "Percent chance a corridor makes multiple turns",
        "min_num_rivers": "Minimum rivers to generate in this biome",
        "max_num_rivers": "Maximum rivers to generate in this biome",
        "num_up_ladders": "Number of up ladders (exits to previous floor)",
        "num_down_ladders": "Number of down ladders (exits to next floor)",
        "column_percent": "Percent chance a room gets decorative columns",
        # -- Combat --
        "target_character_level": "Average player character level (affects encounter difficulty)",
        "num_player_characters": "Number of player characters (affects encounter XP budget)",
        "room_encounter_percent": "Percent chance each room has a monster encounter",
        "encounter_xp_low_percent": "Minimum encounter XP as percent of party threshold (lower = easier fights)",
        "encounter_xp_high_percent": "Maximum encounter XP as percent of party threshold (higher = harder fights)",
        "monster_filter": "Filter monsters by keyword expression (e.g. 'Undead or Construct')",
        "num_treasures": "Dice expression for number of treasure chests (e.g. 2d4)",
        "num_mimics": "Dice expression for number of mimics disguised as chests (e.g. 1d3-1)",
        "num_bookshelves": "Dice expression for number of bookshelves with lore (e.g. 1d4)",
        "trap_damage_low_multiplier": "Minimum trap damage multiplier (x character level)",
        "trap_damage_high_multiplier": "Maximum trap damage multiplier (x character level)",
        "room_trap_percent": "Percent chance a room has a floor trap",
        "corridor_trap_percent": "Percent chance a corridor has a floor trap",
        "door_trap_percent": "Percent chance a door is trapped",
        "chest_trap_percent": "Percent chance a chest is trapped",
        "door_lock_percent": "Percent chance a door is locked",
        "door_secret_percent": "Percent chance a door is secret (hidden)",
        # -- Features --
        "blacksmith_percent": "Percent chance the dungeon contains a blacksmith NPC room",
        "kryxix_altar_percent": "Percent chance the dungeon contains a Kryxix altar room",
        "ssarthaxx_altar_percent": "Percent chance the dungeon contains a Ssarthaxx altar room",
    }

    def __init__(self, biome_name: str | None = None) -> None:
        self.biome_name: str | None = biome_name
        self.biomes: list[DungeonConfig] = []

        self.ui_ops: list[tuple[str, str | None]] = []
        self.var_keys: set[str] = set()
        self.tk_types: dict[str, type] = {}
        self.tk_label_texts: dict[str, str] = {}
        self.tk_labels: dict[str, Any] = {}
        self.tk_entries: dict[str, Any] = {}
        self.tk_vars: dict[str, Any] = {}
        self.tk_is_long: dict[str, bool] = {}
        self.tk_combobox_values: dict[str, list[str]] = {}
        self.tk_tab_groups: dict[str, str] = {}
        self.tk_global_keys: set[str] = set()

        # Declare all config attributes explicitly for type checker visibility.
        # These are overwritten by add_var calls below.

        # -- Global settings (not per-biome) --
        self.width: int = 0
        self.height: int = 0
        self.num_rooms: int = 0
        self.num_room_embiggenings: int = 0
        self.num_room_wiggles: int = 0
        self.prefer_full_connection: bool = False
        self.min_corridors_per_room: float = 0.0
        self.use_pathfinding_fallback: bool = False
        self.num_rivers: int = 0
        self.min_ladder_distance: int = 0
        self.num_misc_NPCs: str = ""
        self.tts_fog_of_war: bool = False
        self.tts_hidden_zones: bool = False
        self.tts_notecards: bool = False
        self.save_map_image: bool = False

        # -- Terrain --
        self.biome_northness: float = 0.0
        self.biome_southness: float = 0.0
        self.biome_westness: float = 0.0
        self.biome_eastness: float = 0.0
        self.min_room_radius: int = 0
        self.use_maze_layout: bool = False
        self.cavernous_room_percent: float = 0.0
        self.num_erosion_steps: int = 0
        self.structure_style: str = ""
        self.cavern_style: str = ""
        self.room_bright_ratio: float = 0.0
        self.room_dim_ratio: float = 0.0
        self.room_dark_ratio: float = 0.0
        self.corridor_width_1_ratio: float = 0.0
        self.corridor_width_2_ratio: float = 0.0
        self.corridor_width_3_ratio: float = 0.0
        self.corridor_off_center_percent: float = 0.0
        self.corridor_multi_turn_percent: float = 0.0
        self.min_num_rivers: int = 0
        self.max_num_rivers: int = 0
        self.num_up_ladders: int = 0
        self.num_down_ladders: int = 0
        self.column_percent: float = 0.0

        # -- Combat (encounters + traps) --
        self.target_character_level: int = 0
        self.num_player_characters: int = 0
        self.room_encounter_percent: float = 0.0
        self.encounter_xp_low_percent: float = 0.0
        self.encounter_xp_high_percent: float = 0.0
        self.monster_filter: str = ""
        self.num_treasures: str = ""
        self.num_mimics: str = ""
        self.num_bookshelves: str = ""
        self.trap_damage_low_multiplier: int = 0
        self.trap_damage_high_multiplier: int = 0
        self.room_trap_percent: float = 0.0
        self.corridor_trap_percent: float = 0.0
        self.door_trap_percent: float = 0.0
        self.chest_trap_percent: float = 0.0
        self.door_lock_percent: float = 0.0
        self.door_secret_percent: float = 0.0

        # -- Features (special rooms) --
        self.blacksmith_percent: float = 0.0
        self.kryxix_altar_percent: float = 0.0
        self.ssarthaxx_altar_percent: float = 0.0

        # --- Global settings (in_biome=False) ---
        self.add_var("width", 35, in_biome=False)
        self.add_var("height", 35, in_biome=False)
        self.add_var("num_rooms", 12, in_biome=False)
        self.add_var("num_room_embiggenings", 5, in_biome=False)
        self.add_var("num_room_wiggles", 5, in_biome=False)
        self.add_var("prefer_full_connection", True, in_biome=False)
        self.add_var("min_corridors_per_room", 1.1, in_biome=False)
        self.add_var("use_pathfinding_fallback", True, in_biome=False)
        self.add_var("num_rivers", 0, in_biome=False)
        self.add_var("min_ladder_distance", 2, in_biome=False)
        self.add_var("num_misc_NPCs", "1d6-1", in_biome=False)
        self.add_var("tts_fog_of_war", False, in_biome=False)
        self.add_var("tts_hidden_zones", True, in_biome=False)
        self.add_var("tts_notecards", True, in_biome=False)
        self.add_var("save_map_image", True, in_biome=False)

        # --- Terrain subtab ---
        self.add_var(
            "biome_northness", 5.0, biome_only=True, tab_group="Terrain"
        )
        self.add_var(
            "biome_southness", 5.0, biome_only=True, tab_group="Terrain"
        )
        self.add_var(
            "biome_westness", 5.0, biome_only=True, tab_group="Terrain"
        )
        self.add_var(
            "biome_eastness", 5.0, biome_only=True, tab_group="Terrain"
        )
        self.add_var("min_room_radius", 1, tab_group="Terrain")
        self.add_var("use_maze_layout", False, tab_group="Terrain")
        self.add_var("cavernous_room_percent", 50.0, tab_group="Terrain")
        self.add_var("num_erosion_steps", 4, tab_group="Terrain")
        self.add_var(
            "structure_style",
            "dungeon",
            combobox_values=["dungeon", "mossy ruin"],
            is_long=True,
            tab_group="Terrain",
        )
        self.add_var(
            "cavern_style",
            "cavern",
            combobox_values=["cavern", "frozen cavern", "ice", "volcano"],
            is_long=True,
            tab_group="Terrain",
        )
        self.add_var("room_bright_ratio", 5.0, tab_group="Terrain")
        self.add_var("room_dim_ratio", 2.0, tab_group="Terrain")
        self.add_var("room_dark_ratio", 1.0, tab_group="Terrain")
        self.add_var("corridor_width_1_ratio", 1.0, tab_group="Terrain")
        self.add_var("corridor_width_2_ratio", 5.0, tab_group="Terrain")
        self.add_var("corridor_width_3_ratio", 2.0, tab_group="Terrain")
        self.add_var("corridor_off_center_percent", 50.0, tab_group="Terrain")
        self.add_var("corridor_multi_turn_percent", 30.0, tab_group="Terrain")
        self.add_var("min_num_rivers", 0, biome_only=True, tab_group="Terrain")
        self.add_var("max_num_rivers", 9, biome_only=True, tab_group="Terrain")
        self.add_var("num_up_ladders", 1, tab_group="Terrain")
        self.add_var("num_down_ladders", 1, tab_group="Terrain")
        self.add_var("column_percent", 50.0, tab_group="Terrain")

        # --- Combat subtab (encounters + traps) ---
        self.add_var("target_character_level", 7, tab_group="Combat")
        self.add_var("num_player_characters", 5, tab_group="Combat")
        self.add_var("room_encounter_percent", 70.0, tab_group="Combat")
        self.add_var("encounter_xp_low_percent", 50.0, tab_group="Combat")
        self.add_var("encounter_xp_high_percent", 200.0, tab_group="Combat")
        self.add_var(
            "monster_filter",
            "Undead or Flesh Golem",
            is_long=True,
            tab_group="Combat",
        )
        self.add_var("num_treasures", "2d4", tab_group="Combat")
        self.add_var("num_mimics", "1d3-1", tab_group="Combat")
        self.add_var("num_bookshelves", "1d4", tab_group="Combat")
        self.add_var("trap_damage_low_multiplier", 3, tab_group="Combat")
        self.add_var("trap_damage_high_multiplier", 5, tab_group="Combat")
        self.add_var("room_trap_percent", 30.0, tab_group="Combat")
        self.add_var("corridor_trap_percent", 30.0, tab_group="Combat")
        self.add_var("door_trap_percent", 15.0, tab_group="Combat")
        self.add_var("chest_trap_percent", 30.0, tab_group="Combat")
        self.add_var("door_lock_percent", 15.0, tab_group="Combat")
        self.add_var("door_secret_percent", 15.0, tab_group="Combat")

        # --- Features subtab (special rooms) ---
        self.add_var("blacksmith_percent", 30.0, tab_group="Features")
        self.add_var("kryxix_altar_percent", 30.0, tab_group="Features")
        self.add_var("ssarthaxx_altar_percent", 30.0, tab_group="Features")

        self.allow_corridor_intersection = False
        self.max_corridor_attempts = 30000
        self.max_room_attempts = 10

    def add_var(
        self,
        k: str,
        v: Any,
        tk_label: str | None = None,
        is_long: bool = False,
        in_biome: bool = True,
        biome_only: bool = False,
        combobox_values: list[str] | None = None,
        tab_group: str | None = None,
    ) -> None:
        """Register a config variable with its default value and UI metadata."""
        assert k not in self.var_keys
        assert type(v) in [int, float, str, bool]
        if not tk_label:
            tk_label = re.sub("num", "#", k)
            tk_label = re.sub("percent", "%", tk_label)
            tk_label = re.sub("multiplier", "x", tk_label)
            tk_label = re.sub("_", " ", tk_label)
            tk_label = re.sub("tts", "TTS", tk_label)
            tk_label = " ".join(
                [x[0].upper() + x[1:] for x in tk_label.split(" ") if x]
            )
        self.var_keys.add(k)
        self.__dict__[k] = v
        if self.biome_name and not in_biome:
            return
        if not self.biome_name and biome_only:
            return
        self.tk_types[k] = type(v)
        self.tk_label_texts[k] = tk_label
        self.tk_is_long[k] = is_long
        self.ui_ops.append(("config", k))
        if combobox_values:
            self.tk_combobox_values[k] = combobox_values
        if tab_group:
            self.tk_tab_groups[k] = tab_group
        if not in_biome:
            self.tk_global_keys.add(k)

    def _create_var_and_widget(
        self, k: str, parent: Any
    ) -> tuple[Any, Any] | None:
        """Create tkinter var, label, and entry widget for a config key.

        Returns (label_widget, entry_widget) tuple, or None if already
        created.
        """
        if k in self.tk_labels:
            return None
        v = self.__dict__[k]
        label = tk.Label(parent, text=self.tk_label_texts[k])
        self.tk_labels[k] = label
        tip = self.TOOLTIPS.get(k)
        if tip:
            Tooltip(label, tip)
        var = None
        ty = self.tk_types[k]
        if ty is str:
            var = tk.StringVar()
        elif ty is int:
            var = tk.IntVar()
        elif ty is float:
            var = tk.DoubleVar()
        elif ty is bool:
            var = tk.BooleanVar()
        assert var
        var.set(v)
        self.tk_vars[k] = var
        is_combobox = k in self.tk_combobox_values
        if is_combobox:
            combobox = ttk.Combobox(parent, textvariable=var, state="readonly")
            combobox["values"] = tuple(self.tk_combobox_values[k])
            combobox.current(list(self.tk_combobox_values[k]).index(v))
            entry = combobox
        elif ty is bool:
            entry = tk.Checkbutton(parent, variable=var)
        else:
            width = 30 if self.tk_is_long[k] else 5
            entry = tk.Entry(parent, textvariable=var, width=width)
        self.tk_entries[k] = entry
        return label, entry

    def _grid_2wide(self, keys: list[str], parent: Any) -> None:
        """Lay out config widgets in a 2-wide grid inside parent."""
        row = 0
        col = 0
        for k in keys:
            result = self._create_var_and_widget(k, parent)
            if result is None:
                continue
            label, entry = result
            if self.tk_is_long[k]:
                if col == 1:
                    row += 1
                    col = 0
                label.grid(row=row, column=0, columnspan=4, sticky="w")
                row += 1
                entry.grid(row=row, column=0, columnspan=4, sticky="ew")
                row += 1
            else:
                label.grid(row=row, column=col * 2, sticky="e")
                entry.grid(row=row, column=col * 2 + 1, sticky="w")
                col += 1
                if col == 2:
                    col = 0
                    row += 1

    def _grid_layout(
        self,
        layout: list[tuple[str, ...]],
        parent: Any,
        available_keys: set[str],
    ) -> None:
        """Lay out config widgets according to an explicit row layout.

        Each entry in *layout* is a tuple of key names:
        - 2-tuple → two widgets side by side
        - 1-tuple → single widget (full width if long, left column if short)

        Keys present in the layout but absent from *available_keys* produce
        empty spacer rows so that Overall and biome tabs stay aligned.
        """
        row = 0
        for row_spec in layout:
            if len(row_spec) == 2:
                any_placed = False
                for col, k in enumerate(row_spec):
                    if k in available_keys:
                        result = self._create_var_and_widget(k, parent)
                        if result is not None:
                            label, entry = result
                            label.grid(row=row, column=col * 2, sticky="e")
                            entry.grid(row=row, column=col * 2 + 1, sticky="w")
                            any_placed = True
                if not any_placed:
                    parent.grid_rowconfigure(row, minsize=28)
                row += 1
            else:
                k = row_spec[0]
                is_long = self.tk_is_long.get(k, False)
                if k in available_keys:
                    result = self._create_var_and_widget(k, parent)
                    if result is not None:
                        label, entry = result
                        if is_long:
                            label.grid(
                                row=row, column=0, columnspan=4, sticky="w"
                            )
                            row += 1
                            entry.grid(
                                row=row, column=0, columnspan=4, sticky="ew"
                            )
                        else:
                            label.grid(row=row, column=0, sticky="e")
                            entry.grid(row=row, column=1, sticky="w")
                else:
                    if is_long:
                        parent.grid_rowconfigure(row, minsize=28)
                        row += 1
                    parent.grid_rowconfigure(row, minsize=28)
                row += 1

    def make_global_widgets(self, parent: Any) -> None:
        """Create and grid global config widgets in a 2-wide layout."""
        keys = [
            k
            for op, k in self.ui_ops
            if op == "config" and k is not None and k in self.tk_global_keys
        ]
        self._grid_2wide(keys, parent)

    def make_tk_labels_and_entries(self, parent: Any) -> Any:
        """Create nested subtab notebook with laid-out grids per group.

        Returns the subtab notebook widget so callers can synchronize
        tab selection across biomes.
        """
        subtab_notebook = ttk.Notebook(parent)
        subtab_notebook.pack(expand=True, fill="both")

        available: set[str] = set()
        for op, k in self.ui_ops:
            if (
                op == "config"
                and k is not None
                and k not in self.tk_global_keys
            ):
                available.add(k)

        for group_name in self.TAB_GROUPS:
            frame = ttk.Frame(subtab_notebook)
            subtab_notebook.add(frame, text=group_name)
            layout = self.TAB_GROUP_LAYOUTS[group_name]
            self._grid_layout(layout, frame, available)

        return subtab_notebook

    def load_from_tk_entries(self) -> None:
        """Sync config values from the tkinter UI vars."""
        for k, var in self.tk_vars.items():
            self.__dict__[k] = var.get()
        for biome in self.biomes:
            biome.load_from_tk_entries()

    def add_biome(self, biome_name: str) -> DungeonConfig:
        """Create a child biome config inheriting current values."""
        assert biome_name
        biome = DungeonConfig(biome_name=biome_name)
        for k in self.var_keys:
            biome.__dict__[k] = self.__dict__[k]
        self.biomes.append(biome)
        return biome

    def get_biome(self, biome_name: str | None) -> DungeonConfig:
        """Look up a biome by name, or return self if biome_name is None."""
        if biome_name is None:
            return self
        for biome in self.biomes:
            if biome.biome_name == biome_name:
                return biome
        raise KeyError()
