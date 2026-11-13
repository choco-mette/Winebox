"""Low-level terminal raw keyboard input reader."""

import sys


def read_key() -> str:
    """Reads a single keypress from stdin using termios/tty."""
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            seq = sys.stdin.read(2)
            return {"[A": "UP", "[B": "DOWN", "[C": "RIGHT", "[D": "LEFT"}.get(seq, "ESC")
        if ch in ("\r", "\n"):
            return "ENTER"
        if ch == " ":
            return "SPACE"
        if ch == "\x03":
            raise KeyboardInterrupt()
        return {"k": "UP", "K": "UP", "j": "DOWN", "J": "DOWN"}.get(ch, ch)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

