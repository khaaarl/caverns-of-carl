from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk
from typing import Any


class DungeonConfig:
    """All dungeon generation parameters. Also serves as biome sub-configs.

    Each parameter is backed by a tkinter var for the GUI. Biomes are
    child DungeonConfig instances with biome-specific overrides.
    """

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

        # Declare all config attributes explicitly for type checker visibility.
        # These are overwritten by add_var calls below.
        self.width: int = 0
        self.height: int = 0
        self.num_rooms: int = 0
        self.biome_northness: float = 0.0
        self.biome_southness: float = 0.0
        self.biome_westness: float = 0.0
        self.biome_eastness: float = 0.0
        self.min_room_radius: int = 0
        self.num_room_embiggenings: int = 0
        self.num_room_wiggles: int = 0
        self.use_maze_layout: bool = False
        self.cavernous_room_percent: float = 0.0
        self.structure_style: str = ""
        self.cavern_style: str = ""
        self.room_bright_ratio: float = 0.0
        self.room_dim_ratio: float = 0.0
        self.room_dark_ratio: float = 0.0
        self.num_erosion_steps: int = 0
        self.prefer_full_connection: bool = False
        self.min_corridors_per_room: float = 0.0
        self.corridor_width_1_ratio: float = 0.0
        self.corridor_width_2_ratio: float = 0.0
        self.corridor_width_3_ratio: float = 0.0
        self.num_rivers: int = 0
        self.min_num_rivers: int = 0
        self.max_num_rivers: int = 0
        self.num_up_ladders: int = 0
        self.num_down_ladders: int = 0
        self.min_ladder_distance: int = 0
        self.target_character_level: int = 0
        self.num_player_characters: int = 0
        self.num_treasures: str = ""
        self.num_mimics: str = ""
        self.num_bookshelves: str = ""
        self.room_encounter_percent: float = 0.0
        self.encounter_xp_low_percent: float = 0.0
        self.encounter_xp_high_percent: float = 0.0
        self.monster_filter: str = ""
        self.trap_damage_low_multiplier: int = 0
        self.trap_damage_high_multiplier: int = 0
        self.room_trap_percent: float = 0.0
        self.corridor_trap_percent: float = 0.0
        self.door_trap_percent: float = 0.0
        self.chest_trap_percent: float = 0.0
        self.door_lock_percent: float = 0.0
        self.door_secret_percent: float = 0.0
        self.blacksmith_percent: float = 0.0
        self.kryxix_altar_percent: float = 0.0
        self.ssarthaxx_altar_percent: float = 0.0
        self.column_percent: float = 0.0
        self.num_misc_NPCs: str = ""
        self.tts_fog_of_war: bool = False
        self.tts_hidden_zones: bool = False
        self.tts_notecards: bool = False
        self.save_map_image: bool = False

        self.add_var("width", 35, in_biome=False)
        self.add_var("height", 35, in_biome=False)
        self.add_var("num_rooms", 12, in_biome=False)
        self.add_var("biome_northness", 5.0, biome_only=True)
        self.add_var("biome_southness", 5.0, biome_only=True)
        self.add_var("biome_westness", 5.0, biome_only=True)
        self.add_var("biome_eastness", 5.0, biome_only=True)
        self.add_var("min_room_radius", 1)
        self.add_var("num_room_embiggenings", 5, in_biome=False)
        self.add_var("num_room_wiggles", 5, in_biome=False)
        self.add_var("use_maze_layout", False)
        self.add_var("cavernous_room_percent", 50.0)
        self.add_var(
            "structure_style",
            "dungeon",
            combobox_values=["dungeon", "mossy ruin"],
            is_long=True,
        )
        self.add_var(
            "cavern_style",
            "cavern",
            combobox_values=["cavern", "frozen cavern", "ice", "volcano"],
            is_long=True,
        )
        self.add_var("room_bright_ratio", 5.0)
        self.add_var("room_dim_ratio", 2.0)
        self.add_var("room_dark_ratio", 1.0)
        self.add_var("num_erosion_steps", 4)
        self.add_var("prefer_full_connection", True, in_biome=False)
        self.add_var("min_corridors_per_room", 1.1, in_biome=False)
        self.add_var("corridor_width_1_ratio", 1.0)
        self.add_var("corridor_width_2_ratio", 5.0)
        self.add_var("corridor_width_3_ratio", 2.0)
        self.add_var("num_rivers", 0, in_biome=False)
        self.add_var("min_num_rivers", 0, biome_only=True)
        self.add_var("max_num_rivers", 9, biome_only=True)
        self.add_var("num_up_ladders", 1)
        self.add_var("num_down_ladders", 1)
        self.add_var("min_ladder_distance", 2, in_biome=False)
        self.ui_ops.append(("next group", None))
        self.add_var("target_character_level", 7)
        self.add_var("num_player_characters", 5)
        self.add_var("num_treasures", "2d4")
        self.add_var("num_mimics", "1d3-1")
        self.add_var("num_bookshelves", "1d4")
        self.add_var("room_encounter_percent", 70.0)
        self.add_var("encounter_xp_low_percent", 50.0)
        self.add_var("encounter_xp_high_percent", 200.0)
        self.add_var("monster_filter", "Undead or Flesh Golem", is_long=True)
        self.add_var("trap_damage_low_multiplier", 3)
        self.add_var("trap_damage_high_multiplier", 5)
        self.add_var("room_trap_percent", 30.0)
        self.add_var("corridor_trap_percent", 30.0)
        self.add_var("door_trap_percent", 15.0)
        self.add_var("chest_trap_percent", 30.0)
        self.add_var("door_lock_percent", 15.0)
        self.add_var("door_secret_percent", 15.0)
        self.add_var("blacksmith_percent", 30.0)
        self.add_var("kryxix_altar_percent", 30.0)
        self.add_var("ssarthaxx_altar_percent", 30.0)
        self.add_var("column_percent", 50.0)
        self.add_var("num_misc_NPCs", "1d6-1", in_biome=False)
        self.add_var("tts_fog_of_war", False, in_biome=False)
        self.add_var("tts_hidden_zones", True, in_biome=False)
        self.add_var("tts_notecards", True, in_biome=False)
        self.add_var("save_map_image", True, in_biome=False)
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

    def make_tk_labels_and_entries(self, parent: Any) -> None:
        """Create tkinter label and entry widgets for all config variables."""
        row = 0
        group = 0
        for op, k in self.ui_ops:
            if op == "next group":
                group += 1
                row = 0
            if op != "config":
                continue
            assert k is not None
            if k in self.tk_labels:
                continue
            v = self.__dict__[k]
            self.tk_labels[k] = tk.Label(parent, text=self.tk_label_texts[k])
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
                combobox = ttk.Combobox(
                    parent, textvariable=var, state="readonly"
                )
                combobox["values"] = tuple(self.tk_combobox_values[k])
                combobox.current(list(self.tk_combobox_values[k]).index(v))
                self.tk_entries[k] = combobox
            elif ty is bool:
                self.tk_entries[k] = tk.Checkbutton(parent, variable=var)
            else:
                if self.tk_is_long[k]:
                    self.tk_entries[k] = tk.Entry(
                        parent, textvariable=var, width=30
                    )
                else:
                    self.tk_entries[k] = tk.Entry(
                        parent, textvariable=var, width=5
                    )
            if self.tk_is_long[k]:
                self.tk_labels[k].grid(row=row, column=group * 2, columnspan=2)
                self.tk_entries[k].grid(
                    row=row + 1, column=group * 2, columnspan=2
                )
                row += 2
            else:
                self.tk_labels[k].grid(row=row, column=group * 2, sticky="e")
                self.tk_entries[k].grid(
                    row=row, column=group * 2 + 1, sticky="w"
                )
                row += 1

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
