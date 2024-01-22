import datetime
import re
import random
import traceback

import tkinter as tk
import tkinter.font
from tkinter import scrolledtext
from tkinter import ttk

import lib.config
import lib.dungeon
import lib.monster
import lib.pdf
import lib.tts as tts
from lib.utils import StyledString


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
    tk_text.tag_configure("defaultish", **default_tag_kwargs)
    tag_db[None] = "defaultish"
    tag_names = set()
    s = StyledString(s)
    lines = s.split("\n")
    for lineix, line in enumerate(lines):
        for ix, c in enumerate(line.chars):
            tk_text.insert(tk.END, c.c)
            tag_name = None
            if c.style not in tag_db:
                while tag_name is None or tag_name in tag_names:
                    tag_name = f"s{random.randrange(1000000)}"
                tag_names.add(tag_name)
                d = dict(default_tag_kwargs or {})
                d["foreground"] = c.style.color_hex()
                d["background"] = "#000000"
                if c.style.is_bold:
                    d["font"] = bold_font
                elif c.style.is_underline:
                    d["font"] = underline_font
                tk_text.tag_configure(tag_name, **d)
                tag_db[c.style] = tag_name
            tag_name = tag_db[c.style]
            tk_text.tag_add(tag_name, f"{lineix+1}.{ix}", f"{lineix+1}.{ix+1}")
        if lineix < len(lines) - 1:
            tk_text.insert(tk.END, "\n")
            if style_newlines:
                tk_text.tag_add(tag_name, f"{lineix+1}.{ix}", tk.END)


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

    # dungeon config notebook
    config_notebook = ttk.Notebook(left_frame)
    config_notebook.pack(expand=True, fill="both")
    default_config_frame = ttk.Frame(config_notebook)
    config_notebook.add(default_config_frame, text="Overall")
    config.make_tk_labels_and_entries(default_config_frame)

    def add_biome(*args, **kwargs):
        switch_to_tab = kwargs.get("switch_to_tab", True)
        biome_name = f"Biome {1+len(config.biomes)}"
        config.load_from_tk_entries()
        biome_config = config.add_biome(biome_name=biome_name)
        biome_config.biome_northness = float(random.randrange(1, 10))
        biome_config.biome_southness = float(random.randrange(1, 10))
        biome_config.biome_westness = float(random.randrange(1, 10))
        biome_config.biome_eastness = float(random.randrange(1, 10))
        biome_config.num_up_ladders = 0
        biome_config.num_down_ladders = 0
        biome_config.blacksmith_percent = 0
        biome_config.kryxix_altar_percent = 0
        biome_config.ssarthaxx_altar_percent = 0
        biome_config_frame = ttk.Frame(config_notebook)
        config_notebook.add(biome_config_frame, text=biome_name)
        biome_config.make_tk_labels_and_entries(biome_config_frame)
        if switch_to_tab:
            config_notebook.select(len(config.biomes))

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
                doc = room.description(df, verbose=True)
                text_output.append(f"***{doc.flat_header()}***")
                text_output.append(doc.flat_body(separator="\n\n"))
                text_output.append("")
            for corridor in sorted(df.corridors, key=lambda x: x.name or ""):
                if not corridor.is_nontrivial(df):
                    continue
                doc = corridor.description(df, verbose=True)
                text_output.append(f"***{doc.flat_header()}***")
                text_output.append(doc.flat_body(separator="\n\n"))
                text_output.append("")
            for npc in sorted(df.npcs, key=lambda x: x.name):
                doc = npc.doc()
                text_output.append(f"***{doc.flat_header()}***")
                text_output.append(doc.flat_body(separator="\n\n"))
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
            StyledString("\n").join(text_output),
            {"foreground": "#fff", "background": "#000"},
        )

    def save_dungeon(*args, **kwargs):
        if not dungeon_history:
            return
        text_output = ["\n"]
        try:
            df = dungeon_history[-1]
            now = datetime.datetime.now()
            name = f"Caverns of Carl {now:%Y-%m-%dT%H-%M-%S%z}"
            pdf_filename = lib.pdf.produce_pdf_if_possible(df, name)
            if pdf_filename:
                text_output.append(
                    f"Created PDF information document at {pdf_filename}"
                )
            else:
                text_output.append(
                    "The python library `pdflab` is not installed, so no PDF information document will be created."
                )
            blob = tts.dungeon_to_tts_blob(df, name, pdf_filename=pdf_filename)
            tts_filename = tts.save_tts_blob(blob)
            text_output.append(f"Saved TTS file to {tts_filename}")
        except Exception as e:
            text_output.append("\n")
            text_output.append(traceback.format_exc())
        chest_info_text.insert(tk.END, StyledString("\n").join(text_output))
        chest_info_text.see(tk.END)

    operation_frame = tk.Frame(left_frame)
    add_biome_button = tk.Button(
        operation_frame, text="Add Biome", command=add_biome
    )
    add_biome_button.grid(row=0, column=0)
    generate_button = tk.Button(
        operation_frame, text="Generate", command=new_preview
    )
    generate_button.grid(row=0, column=1)
    save_button = tk.Button(
        operation_frame, text="Save to TTS", command=save_dungeon
    )
    save_button.grid(row=0, column=2)
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
