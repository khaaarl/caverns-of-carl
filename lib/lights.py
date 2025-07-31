import random

import lib.tts as tts
from lib.tile import (
    WallTile,
)


class LightSource:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.roomix = None
        self.corridorix = None
        self.ix = None

    def tts_object(self, df):
        raise NotImplementedError()


class WallSconce(LightSource):
    def tts_object(self, df):
        obj = tts.reference_object("Horn Candle Sconce")
        df.tts_xz(self.x, self.y, obj)
        obj["Transform"]["rotX"] = 0.0
        obj["Transform"]["rotY"] = 0.0
        obj["Transform"]["rotZ"] = 0.0
        obj["Transform"]["posY"] = 1.8
        obj["Transform"]["scaleX"] = 0.7
        obj["Transform"]["scaleY"] = 0.7
        obj["Transform"]["scaleZ"] = 0.7
        obj["Locked"] = True
        # Rotate away from wall
        posrots = [(0, 1, 90), (1, 0, 180), (0, -1, 270), (-1, 0, 0)]
        random.shuffle(posrots)
        for dx, dy, r in posrots:
            if isinstance(df.tiles[self.x + dx][self.y + dy], WallTile):
                obj["Transform"]["rotY"] += r
                obj["Transform"]["posX"] += 0.5 * dx
                obj["Transform"]["posZ"] += 0.5 * dy
                break
        # Currently the attached light ... doesn't look very good.
        del obj["ChildObjects"]
        return obj


class GlowingMushrooms(LightSource):
    def tts_object(self, df):
        obj = tts.reference_object("Blue Mushrooms for Glowing")
        df.tts_xz(self.x, self.y, obj)
        obj["Transform"]["rotX"] = 0.0
        obj["Transform"]["rotY"] = random.randrange(360) * 1.0
        obj["Transform"]["rotZ"] = 0.0
        obj["Transform"]["posY"] = 2.0
        obj["Transform"]["scaleX"] = 0.5
        obj["Transform"]["scaleY"] = 0.5
        obj["Transform"]["scaleZ"] = 0.5
        obj["Locked"] = True
        # Currently the attached light ... doesn't look very good.
        del obj["ChildObjects"]
        return obj
