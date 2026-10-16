"""Explicit action representation. Low-level actions are Enum members;
strategic (MCTS) actions are added in Phase 6."""
from enum import Enum


class Action(Enum):
    MOVE_UP = "MOVE_UP"
    MOVE_DOWN = "MOVE_DOWN"
    MOVE_LEFT = "MOVE_LEFT"
    MOVE_RIGHT = "MOVE_RIGHT"
    ATTACK = "ATTACK"
    RESCUE = "RESCUE"
    USE_RADAR = "USE_RADAR"
    USE_SPEED = "USE_SPEED"
    USE_TELEPORT = "USE_TELEPORT"
    USE_FREEZE = "USE_FREEZE"
    FINAL_ATTACK = "FINAL_ATTACK"
    WAIT = "WAIT"


# Grid coordinates are (x, y): x = column, y = row, (0,0) is top-left. "Up" is y-1.
MOVE_DELTAS = {
    Action.MOVE_UP: (0, -1),
    Action.MOVE_DOWN: (0, 1),
    Action.MOVE_LEFT: (-1, 0),
    Action.MOVE_RIGHT: (1, 0),
}
