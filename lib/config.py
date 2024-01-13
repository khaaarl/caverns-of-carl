import re

import tkinter as tk


class DungeonConfig:
    def __init__(self):
        self.ui_ops = []
        self.var_keys = set()
        self.tk_types = {}
        self.tk_label_texts = {}
        self.tk_labels = {}
        self.tk_entries = {}
        self.tk_vars = {}
        self.tk_is_long = {}

        self.add_var("width", 35)
        self.add_var("height", 35)
        self.add_var("num_rooms", 12)
        self.add_var("min_room_radius", 1)
        self.add_var("num_room_embiggenings", 5)
        self.add_var("num_room_wiggles", 5)
        self.add_var("cavernous_room_percent", 50.0)
        self.add_var("room_bright_ratio", 5.0)
        self.add_var("room_dim_ratio", 2.0)
        self.add_var("room_dark_ratio", 1.0)
        self.add_var("num_erosion_steps", 4)
        self.add_var("prefer_full_connection", True)
        self.add_var("min_corridors_per_room", 1.1)
        self.add_var("corridor_width_1_ratio", 1.0)
        self.add_var("corridor_width_2_ratio", 5.0)
        self.add_var("corridor_width_3_ratio", 2.0)
        self.add_var("num_up_ladders", 1)
        self.add_var("num_down_ladders", 1)
        self.add_var("min_ladder_distance", 2)
        self.add_var("tts_fog_of_war", False)
        self.add_var("tts_hidden_zones", True)
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
        self.add_var("room_trap_percent", 30.0)
        self.add_var("corridor_trap_percent", 30.0)
        self.add_var("door_trap_percent", 15.0)
        self.add_var("chest_trap_percent", 30.0)
        self.add_var("blacksmith_percent", 30.0)
        self.allow_corridor_intersection = False
        self.min_ladder_distance = 2
        self.max_corridor_attempts = 30000
        self.max_room_attempts = 10

    def add_var(self, k, v, tk_label=None, is_long=False):
        assert k not in self.var_keys
        assert type(v) in [int, float, str, bool]
        if not tk_label:
            tk_label = re.sub("num", "#", k)
            tk_label = re.sub("percent", "%", tk_label)
            tk_label = re.sub("_", " ", tk_label)
            tk_label = re.sub("tts", "TTS", tk_label)
            tk_label = " ".join(
                [x[0].upper() + x[1:] for x in tk_label.split(" ") if x]
            )
        self.var_keys.add(k)
        self.__dict__[k] = v
        self.tk_types[k] = type(v)
        self.tk_label_texts[k] = tk_label
        self.tk_is_long[k] = is_long
        self.ui_ops.append(("config", k))

    def make_tk_labels_and_entries(self, parent):
        row = 0
        group = 0
        for op, k in self.ui_ops:
            if op == "next group":
                group += 1
                row = 0
            if op != "config":
                continue
            if k in self.tk_labels:
                continue
            v = self.__dict__[k]
            self.tk_labels[k] = tk.Label(parent, text=self.tk_label_texts[k])
            var = None
            ty = self.tk_types[k]
            if ty == str:
                var = tk.StringVar()
            elif ty == int:
                var = tk.IntVar()
            elif ty == float:
                var = tk.DoubleVar()
            elif ty == bool:
                var = tk.BooleanVar()
            assert var
            var.set(v)
            self.tk_vars[k] = var
            if ty == bool:
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

    def load_from_tk_entries(self):
        for k, var in self.tk_vars.items():
            self.__dict__[k] = var.get()
