# Caverns of Carl

A (very inchoate) tool to generate random D&D 5e dungeons, and produce save games for Tabletop Simulator additive load.

![UI Screenshot](https://raw.githubusercontent.com/khaaarl/caverns-of-carl/main/docs/screenshots/Screenshot-2024-01-09%20173040.jpg)

## How to Use

1. Download by clicking the green Code button, then Download Zip.
2. Install Python if you haven't already.
3. Run `caverns_of_carl.py`.
4. Adjust the configuration fields on the left if desired.
5. Click the Generate button in the bottom left, as many times as you want.
6. Click the Save to TTS button to create a save game in Tabletop Simulator. This will be in your saves directory, assuming it is in the default location. If it is not in the default location ... maybe we'll fix that in a future version sorry.
7. From whichever D&D table you prefer in Tabletop Simulator, additively load your new Caverns of Carl save game.

## Known Bugs and/or Limitations

1. The set of monsters is currently extremely limited. Covering even a large minority of monster manual is very unlikely without some crowdsourced assistance.
2. This can't handle Tabletop Simulator save directories in nonstandard locations.
3. I'd like there to be more "biomes" than this kinda generic dungeon.
4. Bug: the ASCII layout's room numbers currently can clobber room contents. That might be fixed in a near future update.
5. ...and lots more
