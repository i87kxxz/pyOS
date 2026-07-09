"""
pyOS Screen Driver — VGA Text Mode (build-time recording → C runtime)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from .errors import UnsupportedOpError


class Color(Enum):
    BLACK = 0
    BLUE = 1
    GREEN = 2
    CYAN = 3
    RED = 4
    MAGENTA = 5
    BROWN = 6
    LIGHT_GRAY = 7
    DARK_GRAY = 8
    LIGHT_BLUE = 9
    LIGHT_GREEN = 10
    LIGHT_CYAN = 11
    LIGHT_RED = 12
    LIGHT_MAGENTA = 13
    YELLOW = 14
    WHITE = 15


COLOR_NAMES = {
    "black": Color.BLACK,
    "blue": Color.BLUE,
    "green": Color.GREEN,
    "cyan": Color.CYAN,
    "red": Color.RED,
    "magenta": Color.MAGENTA,
    "brown": Color.BROWN,
    "light_gray": Color.LIGHT_GRAY,
    "gray": Color.LIGHT_GRAY,
    "dark_gray": Color.DARK_GRAY,
    "light_blue": Color.LIGHT_BLUE,
    "light_green": Color.LIGHT_GREEN,
    "light_cyan": Color.LIGHT_CYAN,
    "light_red": Color.LIGHT_RED,
    "light_magenta": Color.LIGHT_MAGENTA,
    "yellow": Color.YELLOW,
    "white": Color.WHITE,
}


@dataclass
class ScreenConfig:
    width: int = 80
    height: int = 25
    vga_address: int = 0xB8000


def _require_ascii(text: str, api: str) -> str:
    try:
        text.encode("ascii")
    except UnicodeEncodeError as e:
        raise UnsupportedOpError(
            api,
            "VGA text mode is CP437/ASCII only. Use ASCII characters (no UTF-8/Arabic in Screen.print).",
        ) from e
    return text


def _parse_color(name: Optional[str], default: Color) -> Color:
    if name is None:
        return default
    key = name.lower()
    if key not in COLOR_NAMES:
        raise ValueError(
            f"Unknown color {name!r}. Valid: {', '.join(sorted(COLOR_NAMES))}"
        )
    return COLOR_NAMES[key]


def _check_pos(row: Optional[int], col: Optional[int], api: str) -> None:
    if row is not None and (row < 0 or row >= 25):
        raise ValueError(f"{api}: row must be 0..24, got {row}")
    if col is not None and (col < 0 or col >= 80):
        raise ValueError(f"{api}: col must be 0..79, got {col}")


class Screen:
    _config = ScreenConfig()
    _cursor_row: int = 0
    _cursor_col: int = 0
    _foreground: Color = Color.WHITE
    _background: Color = Color.BLACK
    _operations: list = []

    @classmethod
    def clear(cls) -> None:
        cls._cursor_row = 0
        cls._cursor_col = 0
        cls._operations.append({"type": "clear"})

    @classmethod
    def print(
        cls,
        text: str,
        row: Optional[int] = None,
        col: Optional[int] = None,
        color: Optional[str] = None,
        background: Optional[str] = None,
        newline: bool = True,
    ) -> None:
        text = _require_ascii(str(text), "Screen.print")
        _check_pos(row, col, "Screen.print")
        if row is not None:
            cls._cursor_row = row
        if col is not None:
            cls._cursor_col = col
        fg = _parse_color(color, cls._foreground)
        bg = _parse_color(background, cls._background)
        cls._operations.append(
            {
                "type": "print",
                "text": text,
                "row": cls._cursor_row,
                "col": cls._cursor_col,
                "foreground": fg.value,
                "background": bg.value,
                "newline": newline,
            }
        )
        if newline:
            cls._cursor_row += 1
            cls._cursor_col = 0
        else:
            cls._cursor_col += len(text)
            if cls._cursor_col >= cls._config.width:
                cls._cursor_row += cls._cursor_col // cls._config.width
                cls._cursor_col %= cls._config.width

    @classmethod
    def print_at(
        cls,
        text: str,
        row: int,
        col: int,
        color: Optional[str] = None,
        background: Optional[str] = None,
    ) -> None:
        cls.print(text, row=row, col=col, color=color, background=background, newline=True)

    @classmethod
    def print_char(
        cls,
        char: str,
        row: int,
        col: int,
        color: Optional[str] = None,
        background: Optional[str] = None,
    ) -> None:
        _check_pos(row, col, "Screen.print_char")
        ch = (char[0] if char else " ")
        _require_ascii(ch, "Screen.print_char")
        fg = _parse_color(color, cls._foreground)
        bg = _parse_color(background, cls._background)
        cls._operations.append(
            {
                "type": "print_char",
                "char": ch,
                "row": row,
                "col": col,
                "foreground": fg.value,
                "background": bg.value,
            }
        )

    @classmethod
    def set_color(cls, foreground: str, background: str = "black") -> None:
        cls._foreground = _parse_color(foreground, Color.WHITE)
        cls._background = _parse_color(background, Color.BLACK)
        cls._operations.append(
            {
                "type": "set_color",
                "foreground": cls._foreground.value,
                "background": cls._background.value,
            }
        )

    @classmethod
    def set_cursor(cls, row: int, col: int) -> None:
        _check_pos(row, col, "Screen.set_cursor")
        cls._cursor_row = row
        cls._cursor_col = col
        cls._operations.append({"type": "set_cursor", "row": row, "col": col})

    @classmethod
    def get_cursor(cls) -> Tuple[int, int]:
        return (cls._cursor_row, cls._cursor_col)

    @classmethod
    def scroll_up(cls, lines: int = 1) -> None:
        cls._operations.append({"type": "scroll_up", "lines": max(1, int(lines))})

    @classmethod
    def scroll_down(cls, lines: int = 1) -> None:
        cls._operations.append({"type": "scroll_down", "lines": max(1, int(lines))})

    @classmethod
    def enable_cursor(cls) -> None:
        cls._operations.append({"type": "enable_cursor"})

    @classmethod
    def disable_cursor(cls) -> None:
        cls._operations.append({"type": "disable_cursor"})

    @classmethod
    def get_width(cls) -> int:
        return cls._config.width

    @classmethod
    def get_height(cls) -> int:
        return cls._config.height

    @classmethod
    def _reset(cls) -> None:
        cls._cursor_row = 0
        cls._cursor_col = 0
        cls._foreground = Color.WHITE
        cls._background = Color.BLACK
        cls._operations = []

    @classmethod
    def _get_operations(cls) -> list:
        return cls._operations.copy()
