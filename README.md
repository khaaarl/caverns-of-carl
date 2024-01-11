# Caverns of Carl

A (very inchoate) tool to generate random D&D 5e dungeons, and produce save games for Tabletop Simulator additive load.

UI Example Screenshot             |  In-TTS Example Screenshot
:-------------------------:|:-------------------------:
![UI Screenshot](https://raw.githubusercontent.com/khaaarl/caverns-of-carl/main/docs/screenshots/Screenshot-2024-01-09%20173040.jpg)  |  ![TTS Screenshot](https://raw.githubusercontent.com/khaaarl/caverns-of-carl/main/docs/screenshots/20240105213607_1.jpg)

## How to Use

1. [Download the Caverns of Carl zip archive](https://github.com/khaaarl/caverns-of-carl/zipball/main/) (or click the green Code button, then Download Zip), then unzip it.
2. [Install Python](https://www.python.org/downloads/) if you haven't already.
3. Run `caverns_of_carl.py`.
4. Adjust the configuration fields on the left if desired.
5. Click the Generate button in the bottom left, as many times as you want.
6. Click the Save to TTS button to create a save game in Tabletop Simulator. This will be in your saves directory, assuming it is in the default location. If it is not in the default location ... maybe I'll fix that in a future version sorry.
7. From whichever D&D table you prefer in Tabletop Simulator, additively load your new Caverns of Carl save game.

### As a Dungeon Master / Game Master (DM/GM)

1. Pick either the players' starting room: typically either the ladder-up room or hatch down room.
2. For any room the players enter or view:
   1. Delete or move any notecards (these are notes for you, the DM)
   2. Hit F3 or click the 3rd tool from the top to get to the hidden zone tool
   3. Hover your mouse over each of the hidden zones that cover the room and its surrounding walls and doors, and hit the Delete key on each. You pay find it helpful to change perspective to top down (P key).
3. Monsters have their HP in their names already. You can increment or decrement their HP while hovering over them with numpad 2 or 3, or just edit it directly. If you prefer monsters not to reveal their names or health to the players, feel free to just mass select monsters and delete the names.
4. Mimics are in chests' state 2. If a mimic is revealed, you must detach it from the tile it is on: hit F6 or click the 6th tool from the top to get to the joint tool, then click on the tile and drag away to the sky or other 

### As a Player

1. When opening a chest or door, move your miniature to the location it would be standing, then while hovering over the tile and hit 2 on the keyboard (not number pad) to change its state. This represents your character opening the chest or door. There could be a surprise!

## Known Bugs and/or Limitations

1. The set of monsters is currently extremely limited. Covering even a large minority of monster manual is very unlikely without some crowdsourced assistance.
2. The TTS Fog of War doesn't seem to play very well with this, and I don't understand it. The revealers don't always reveal obvious things, like the floor, and often reveal through walls. I'd like it to work but I'd need some outside help I think. I saw CoColonCleaner's mod's walls be constructed out of, I think, just square blocks to block line of sight, but I don't know how that works. For now, the hidden zones work well at least, so I've made that the default.
3. This can't handle Tabletop Simulator save directories in nonstandard locations (yet).
4. I'd like there to be more "biomes" than this kinda generic dungeon.
5. ...and lots more
