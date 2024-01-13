import lib.tts as tts
from lib.tile import CorridorFloorTile, WallTile


class SpecialFeature:
    def __init__(self):
        self.roomix = None

    def description(self, df):
        """A string description of the special feature.

        This will show up in notes for its room."""
        raise NotImplementedError()

    def score_rooms(self, df):
        """Helps decide which room in which to place this feature.

        Returns a dict of room.ix : score. Score is a number (higher
        is better), and must be > 0. This dict will only include rooms that allow valid
        placement."""
        return [1.0 for _ in df.rooms]

    def tts_objects(self, df):
        # return []
        raise NotImplementedError()

    def ascii_chars(self, df):
        """Returns a list of (x, y, char) tuples."""
        raise NotImplementedError()

    def allows_enemies(self):
        return False

    def allows_other_features(self, other_features=[]):
        return False

    def allows_treasure(self):
        return False

    def allows_traps(self):
        return False


class Blacksmith(SpecialFeature):
    def description(self, df):
        return "The blacksmith Andrus of Eastora has set up shop here."

    def score_rooms(self, df):
        output = {}
        for room in df.rooms:
            score = 1.0
            # Prefer being in an enclosed dungeon room
            if room.tile_style() != "dungeon":
                score *= 0.5
            if not room.is_fully_enclosed_by_doors():
                score *= 0.4
            # prefer being in a bright room
            if room.light_level == "dark":
                score *= 0.1
            elif room.light_level == "dim":
                score *= 0.3
            # prefer cozy rooms
            score *= 9.0 / room.total_space()
            if not self._thing_coords(df, room):
                score = -1  # couldn't find places for my things!
            if score > 0.0:
                output[room.ix] = score
        return output

    def _thing_coords(self, df, room):
        for sx, sy in room.tile_coords():
            stile = df.get_tile(sx, sy)
            if stile.is_move_blocking():
                continue
            smith_near_wall = False
            smith_near_corridor = False
            ax, ay = None, None
            for atile in df.neighbor_tiles(stile):
                smith_near_wall |= isinstance(atile, WallTile)
            for atile in df.neighbor_tiles(stile, diagonal=True):
                smith_near_corridor |= isinstance(atile, CorridorFloorTile)
            if smith_near_corridor or not smith_near_wall:
                continue
            for atile in df.neighbor_tiles(stile):
                anvil_obstructed = atile.is_move_blocking()
                for nt in df.neighbor_tiles(atile, diagonal=True):
                    anvil_obstructed |= nt.is_move_blocking()
                if not anvil_obstructed:
                    ax, ay = atile.x, atile.y
                    break
            if ax:
                return {"smith_coords": (sx, sy), "anvil_coords": (ax, ay)}
        return None

    def ascii_chars(self, df):
        """Returns a list of (x, y, char) tuples."""
        room = df.rooms[self.roomix]
        thing_coords = self._thing_coords(df, room)
        sx, sy = thing_coords["smith_coords"]
        ax, ay = thing_coords["anvil_coords"]
        return [(sx, sy, "[1;97m&"), (ax, ay, "[1;97m]")]

    def tts_objects(self, df):
        room = df.rooms[self.roomix]
        thing_coords = self._thing_coords(df, room)
        sx, sy = thing_coords["smith_coords"]
        ax, ay = thing_coords["anvil_coords"]
        monster = tts.reference_object("Lich A")
        smith = tts.reference_object("Blacksmith on 1inch")
        smith["LuaScript"] = monster["LuaScript"]
        smith["Nickname"] = "Blacksmith Andrus of Eastora"
        anvil = tts.reference_object("Blacksmith's Anvil")
        if sx > ax:
            smith["Transform"]["rotY"] += 90.0
            anvil["Transform"]["rotY"] += 90.0
        if sx < ax:
            smith["Transform"]["rotY"] -= 90.0
            anvil["Transform"]["rotY"] -= 90.0
        if sy < ay:
            smith["Transform"]["rotY"] += 180.0
            anvil["Transform"]["rotY"] += 180.0
        df.tts_xz(sx, sy, smith)
        df.tts_xz(ax, ay, anvil)
        return [smith, anvil]
