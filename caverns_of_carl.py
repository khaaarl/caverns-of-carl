"""Caverns of Carl

Vague plan of cool things
* room placement (done)
* connections/corridors (done)
* tts save file output (done)
* tts fog of war (done)
* stairs up & down (done)
* monster placement (done)
* treasure chests (done)
* tts fog of war with individual room coverage (done)
* monster encounter constraint: max_per_floor, Backline, Homogenous (done)
* double/triple wide hallways, double/triple doors (done)
* bookshelves (done)
* notecards per room/corridor (done)
* random traps in hallways or rooms (done)
* monster filter expressions, e.g. undead or "flesh golem" (done)
* UI in tkinter of some sort (done)
* monster encounter constraint: Frontline (done)
* cavernous rooms (done)
* room lighting, denoted with floor tile tint & description
* ladder configurable bfs distance check
* cavernous corridors should have some erosion, and not be straight
* DM toolpanel in TTS, including button to delete everything. Move health increment/decrement to this singleton object
* Prepared wandering monster encounters in the DM hidden zone (also relevant for traps that summon)
* GPT API integration?
* locked doors and keys?
* secret doors?
* themes and tilesets?
* rivers?
* altars?
* cosmetic doodads like wall sconces and bloodstains


TTS Dungeon or monster resources used:
https://steamcommunity.com/sharedfiles/filedetails/?id=375338382
https://steamcommunity.com/sharedfiles/filedetails/?id=2874146220
https://steamcommunity.com/sharedfiles/filedetails/?id=2917302184
https://steamcommunity.com/sharedfiles/filedetails/?id=2903159179
https://steamcommunity.com/sharedfiles/filedetails/?id=2300627680
https://aos-tts.github.io/Stormvault/
"""

import re
import traceback

try:
    import tkinter as _tk_test
except:
    print(
        "Failed to load tcl/tk. You may need to install additional modules (e.g. python3-tk if you are on Ubuntu)\nPress enter to exit"
    )
    input()
    exit()

import tkinter as tk
import tkinter.font
from tkinter import scrolledtext
from tkinter import ttk

import lib.config
import lib.dungeon
import lib.monster
import lib.tts as tts


def set_tk_text(tk_text, s, default_tag_kwargs={}, style_newlines=False):
    tk_text.delete("1.0", tk.END)
    for tag in tk_text.tag_names():
        tk_text.tag_delete(tag)
    font_info = tkinter.font.nametofont(tk_text.cget("font")).actual()
    bold_font_info = dict(font_info)
    bold_font_info["weight"] = "bold"
    bold_font = tkinter.font.Font(**bold_font_info)
    underline_font_info = dict(font_info)
    underline_font_info["underline"] = True
    underline_font = tkinter.font.Font(**bold_font_info)
    tag_db = {}
    if default_tag_kwargs:
        tk_text.tag_configure("defaultish", **default_tag_kwargs)
        tag_db[(-1, -1)] = "defaultish"
    lines = s.split("\n")
    for lineix, line in enumerate(lines):
        ix = 0
        colored_chars = []
        while ix < len(line):
            if ix + 6 < len(line):
                possible_code = line[ix : ix + 6]
                if re.match(r"^\[[0-9];[0-9][0-9]m$", possible_code):
                    style = int(possible_code[1])
                    color = int(possible_code[3:5])
                    colored_chars.append((line[ix + 6], style, color))
                    ix += 7
                    continue
            colored_chars.append((line[ix], None, None))
            ix += 1
        for ix, tup in enumerate(colored_chars):
            c, style, color = tup
            tk_text.insert(tk.END, c)
            if style is None or color is None:
                if not default_tag_kwargs:
                    continue
                style, color = -1, -1
            tag_name = None
            if (style, color) not in tag_db:
                tag_name = f"s{style}c{color}"
                color_hex = {
                    30: "#000",
                    31: "#b00",
                    32: "#0b0",
                    33: "#bb0",
                    34: "#00c",
                    35: "#b0c",
                    36: "#0bc",
                    37: "#bbc",
                    90: "#000",
                    91: "#f00",
                    92: "#0f0",
                    93: "#ff0",
                    94: "#00f",
                    95: "#f0f",
                    96: "#0ff",
                    97: "#fff",
                }[color]
                d = dict(default_tag_kwargs or {})
                d["foreground"] = color_hex
                d["background"] = "#000"
                if style == 1:
                    d["font"] = bold_font
                if style == 4:
                    d["font"] = underline_font
                tk_text.tag_configure(tag_name, **d)
                tag_db[(style, color)] = tag_name
            tag_name = tag_db[(style, color)]
            tk_text.tag_add(tag_name, f"{lineix+1}.{ix}", f"{lineix+1}.{ix+1}")

        if lineix < len(lines) - 1:
            tk_text.insert(tk.END, "\n")
            if style_newlines:
                tk_text.tag_add(tag_name, f"{lineix+1}.{ix}", tk.END)
    pass


def run_ui():
    config = lib.config.DungeonConfig()
    dungeon_history = []

    root = tk.Tk()
    root.title("Caverns of Carl")
    root.columnconfigure(0, weight=1)
    root.columnconfigure(1, weight=1)
    root.columnconfigure(2, weight=1)
    root.rowconfigure(0, weight=1)
    left_frame = tk.Frame(root, borderwidth=2, relief="groove")
    middle_frame = tk.Frame(root, borderwidth=2, relief="groove")
    right_frame = tk.Frame(root, borderwidth=2, relief="groove")
    left_frame.grid(row=0, column=0, sticky="nsew")
    middle_frame.grid(row=0, column=1, sticky="nsew")
    right_frame.grid(row=0, column=2, sticky="nsew")

    # Configuration Frame
    config_label = tk.Label(left_frame, text="Configuration", width=70)
    config_label.pack()

    # dungeon dimensions
    size_frame = tk.Frame(left_frame)
    config.make_tk_labels_and_entries(size_frame)
    size_frame.pack()

    def new_preview(*args, **kwargs):
        set_tk_text(ascii_map_text, "")
        set_tk_text(chest_info_text, "")

        text_output = []
        err = None
        try:
            config.load_from_tk_entries()
            df = lib.dungeon.generate_random_dungeon(config)
            dungeon_history.append(df)

            text_output.append("Floor monster counts:")
            text_output.append(lib.monster.summarize_monsters(df.monsters))
            text_output.append("")
            total_xp = 0
            for room in df.rooms:
                if room.encounter:
                    total_xp += room.encounter.total_xp()
            xp_per_player = int(total_xp / config.num_player_characters)
            text_output.append(
                f"Total floor encounter xp: ~{total_xp:,} (~{xp_per_player:,} per player)"
            )
            text_output.append("")
            for room in df.rooms:
                text_output.append(f"***Room {room.ix}***")
                text_output.append(room.description(df, verbose=True))
                text_output.append("")
            for corridor in sorted(df.corridors, key=lambda x: x.name or ""):
                if not corridor.is_nontrivial(df):
                    continue
                text_output.append(f"***Corridor {corridor.name}***")
                text_output.append(corridor.description(df, verbose=True))
                text_output.append("")
        except Exception as e:
            err = traceback.format_exc()
        if err:
            text_output = [err]
        else:
            ascii = dungeon_history[-1].ascii(colors=True)
            set_tk_text(
                ascii_map_text,
                ascii,
                {"foreground": "#fff", "background": "#000"},
            )
        set_tk_text(
            chest_info_text,
            "\n".join(text_output),
            {"foreground": "#fff", "background": "#000"},
        )

    def save_dungeon(*args, **kwargs):
        if not dungeon_history:
            return
        text_output = ""
        try:
            df = dungeon_history[-1]
            fn = tts.save_tts_blob(lib.dungeon.dungeon_to_tts_blob(df))
            text_output = f"Saved to {fn}"
        except Exception as e:
            text_output = traceback.format_exc()
        chest_info_text.insert(tk.END, f"\n\n{text_output}")
        chest_info_text.see(tk.END)

    operation_frame = tk.Frame(left_frame)
    generate_button = tk.Button(
        operation_frame, text="Generate", command=new_preview
    )
    generate_button.grid(row=0, column=0)
    save_button = tk.Button(
        operation_frame, text="Save to TTS", command=save_dungeon
    )
    save_button.grid(row=0, column=1)
    operation_frame.pack(pady=10)

    ascii_map_label = tk.Label(middle_frame, text="ASCII Map")
    ascii_map_label.pack(pady=10)
    ascii_map_text = scrolledtext.ScrolledText(
        middle_frame,
        wrap=tk.NONE,
        width=57,
        height=35,
        foreground="#fff",
        background="#000",
    )
    # Create a horizontal scrollbar and attach it to the ScrolledText widget
    hscrollbar = tk.Scrollbar(
        middle_frame, orient="horizontal", command=ascii_map_text.xview
    )
    ascii_map_text["xscrollcommand"] = hscrollbar.set
    # Pack the horizontal scrollbar
    hscrollbar.pack(side=tk.BOTTOM, fill=tk.X)
    ascii_map_text.pack(expand=True, fill="both")

    chest_info_label = tk.Label(right_frame, text="Logs and Information")
    chest_info_label.pack(pady=10)

    chest_info_text = scrolledtext.ScrolledText(
        right_frame, foreground="#fff", background="#000"
    )
    chest_info_text.pack(expand=True, fill="both", padx=10, pady=10)

    new_preview()

    root.state("zoomed")
    root.mainloop()


if __name__ == "__main__":
    run_ui()
    exit()
