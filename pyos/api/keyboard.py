"""
pyOS Keyboard — PS/2; build-time ops that map to C keyboard API.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from .errors import UnsupportedOpError


class KeyCode(Enum):
    ESC = 0x01
    ENTER = 0x1C
    LEFT_CTRL = 0x1D
    LEFT_SHIFT = 0x2A
    RIGHT_SHIFT = 0x36
    LEFT_ALT = 0x38
    SPACE = 0x39
    BACKSPACE = 0x0E


SCANCODE_TO_CHAR: Dict[int, str] = {
    0x02: "1",
    0x03: "2",
    0x04: "3",
    0x05: "4",
    0x06: "5",
    0x07: "6",
    0x08: "7",
    0x09: "8",
    0x0A: "9",
    0x0B: "0",
    0x10: "q",
    0x11: "w",
    0x12: "e",
    0x13: "r",
    0x14: "t",
    0x15: "y",
    0x16: "u",
    0x17: "i",
    0x18: "o",
    0x19: "p",
    0x1E: "a",
    0x1F: "s",
    0x20: "d",
    0x21: "f",
    0x22: "g",
    0x23: "h",
    0x24: "j",
    0x25: "k",
    0x26: "l",
    0x2C: "z",
    0x2D: "x",
    0x2E: "c",
    0x2F: "v",
    0x30: "b",
    0x31: "n",
    0x32: "m",
    0x39: " ",
}


@dataclass
class KeyEvent:
    scancode: int
    char: str
    pressed: bool
    shift: bool
    ctrl: bool
    alt: bool


class Keyboard:
    _operations: list = []
    _buffer: list = []
    _shift_pressed: bool = False
    _ctrl_pressed: bool = False
    _alt_pressed: bool = False

    @classmethod
    def read_key(cls) -> None:
        cls._operations.append({"type": "kb_read_key"})

    @classmethod
    def read_char(cls) -> None:
        cls._operations.append({"type": "kb_read_char"})

    @classmethod
    def read_line(cls) -> None:
        cls._operations.append({"type": "kb_read_line"})

    @classmethod
    def wait_key(cls) -> None:
        cls._operations.append({"type": "kb_wait_key"})

    @classmethod
    def clear_buffer(cls) -> None:
        cls._operations.append({"type": "kb_clear_buffer"})

    @classmethod
    def set_repeat_rate(cls, delay_ms: int = 500, rate_cps: int = 10) -> None:
        raise UnsupportedOpError(
            "Keyboard.set_repeat_rate",
            "PS/2 repeat programming is not implemented in the C keyboard driver yet",
        )

    @classmethod
    def is_key_pressed(cls, key: KeyCode) -> bool:
        raise UnsupportedOpError("Keyboard.is_key_pressed", "Use IRQ keypress handler instead")

    @classmethod
    def is_shift_pressed(cls) -> bool:
        return cls._shift_pressed

    @classmethod
    def is_ctrl_pressed(cls) -> bool:
        return cls._ctrl_pressed

    @classmethod
    def is_alt_pressed(cls) -> bool:
        return cls._alt_pressed

    @classmethod
    def _reset(cls) -> None:
        cls._operations = []
        cls._buffer = []
        cls._shift_pressed = False
        cls._ctrl_pressed = False
        cls._alt_pressed = False

    @classmethod
    def _get_operations(cls) -> list:
        return cls._operations.copy()
