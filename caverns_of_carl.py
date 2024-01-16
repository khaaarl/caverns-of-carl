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
* ladder configurable bfs distance check (done)
* blacksmith npc (done)
* PDF output, and have this linked in the TTS game in the DM hidden zone (done)
* cavernous corridors should have some erosion, and not be straight
* DM toolpanel in TTS, including button to delete everything. Move health increment/decrement to this singleton object
* Prepared wandering monster encounters in the DM hidden zone (also relevant for traps that summon)
* More NPCs
* More special rooms, such as with altars
* GPT API integration?
* locked doors and keys?
* secret doors?
* themes and tilesets?
* rivers?
* cosmetic doodads like wall sconces and bloodstains
* multiple biomes, e.g. caverns with kobolds in the northwest, dungeon with something else in the southeast.
* Map side exits
* Maze levels (if this is a thing that can interact with biomes, a maze biome would probably want to be mostly rectangular for simplicity's sake)


TTS Dungeon or monster resources used:
https://steamcommunity.com/sharedfiles/filedetails/?id=375338382
https://steamcommunity.com/sharedfiles/filedetails/?id=2874146220
https://steamcommunity.com/sharedfiles/filedetails/?id=2917302184
https://steamcommunity.com/sharedfiles/filedetails/?id=2903159179
https://steamcommunity.com/sharedfiles/filedetails/?id=2300627680
https://aos-tts.github.io/Stormvault/
"""


try:
    import tkinter as _tk_test
except:
    print(
        "Failed to load tcl/tk. You may need to install additional modules (e.g. python3-tk if you are on Ubuntu)\nPress enter to exit"
    )
    input()
    exit()

import lib.ui


if __name__ == "__main__":
    lib.ui.run_ui()
    exit()
