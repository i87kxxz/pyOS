"""
pyOS Screen Driver - VGA Text Mode
"""

from typing import Optional, Tuple
from enum import Enum
from dataclasses import dataclass


class Color(Enum):
    """VGA Text Mode Colors"""
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


# Color name mapping
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
    """Screen configuration"""
    width: int = 80
    height: int = 25
    vga_address: int = 0xB8000


class Screen:
    """
    VGA Text Mode Screen Driver.
    
    Provides methods to write text to the screen with colors.
    All methods are class methods for easy access.
    
    Example:
        Screen.clear()
        Screen.set_color("green", "black")
        Screen.print("Hello World!")
        Screen.print_at("Position text", row=5, col=10)
    """
    
    _config = ScreenConfig()
    _cursor_row: int = 0
    _cursor_col: int = 0
    _foreground: Color = Color.WHITE
    _background: Color = Color.BLACK
    
    # Internal buffer for compilation
    _operations: list = []
    
    @classmethod
    def clear(cls) -> None:
        """
        Clear the entire screen.
        
        Example:
            Screen.clear()
        """
        cls._cursor_row = 0
        cls._cursor_col = 0
        cls._operations.append({
            "type": "clear",
        })
    
    @classmethod
    def print(
        cls,
        text: str,
        row: Optional[int] = None,
        col: Optional[int] = None,
        color: Optional[str] = None,
        background: Optional[str] = None,
    ) -> None:
        """
        Print text to the screen.
        
        Args:
            text: The text to print
            row: Row position (optional, uses cursor if not specified)
            col: Column position (optional, uses cursor if not specified)
            color: Foreground color name (optional)
            background: Background color name (optional)
        
        Example:
            Screen.print("Hello World!")
            Screen.print("Colored text", color="green")
            Screen.print("At position", row=5, col=10)
        """
        if row is not None:
            cls._cursor_row = row
        if col is not None:
            cls._cursor_col = col
        
        fg = cls._foreground
        bg = cls._background
        
        if color is not None:
            fg = COLOR_NAMES.get(color.lower(), cls._foreground)
        if background is not None:
            bg = COLOR_NAMES.get(background.lower(), cls._background)
        
        cls._operations.append({
            "type": "print",
            "text": text,
            "row": cls._cursor_row,
            "col": cls._cursor_col,
            "foreground": fg.value,
            "background": bg.value,
        })
        
        # Move cursor to next line
        cls._cursor_row += 1
        cls._cursor_col = 0
    
    @classmethod
    def print_at(
        cls,
        text: str,
        row: int,
        col: int,
        color: Optional[str] = None,
        background: Optional[str] = None,
    ) -> None:
        """
        Print text at a specific position.
        
        Args:
            text: The text to print
            row: Row position (0-24)
            col: Column position (0-79)
            color: Foreground color name (optional)
            background: Background color name (optional)
        
        Example:
            Screen.print_at("Hello", row=10, col=35)
        """
        cls.print(text, row=row, col=col, color=color, background=background)
    
    @classmethod
    def print_char(
        cls,
        char: str,
        row: int,
        col: int,
        color: Optional[str] = None,
        background: Optional[str] = None,
    ) -> None:
        """
        Print a single character at a specific position.
        
        Args:
            char: Single character to print
            row: Row position
            col: Column position
            color: Foreground color (optional)
            background: Background color (optional)
        """
        cls._operations.append({
            "type": "print_char",
            "char": char[0] if char else ' ',
            "row": row,
            "col": col,
            "foreground": COLOR_NAMES.get(color, cls._foreground).value if color else cls._foreground.value,
            "background": COLOR_NAMES.get(background, cls._background).value if background else cls._background.value,
        })
    
    @classmethod
    def set_color(cls, foreground: str, background: str = "black") -> None:
        """
        Set the default text colors.
        
        Args:
            foreground: Foreground color name
            background: Background color name (default: black)
        
        Example:
            Screen.set_color("green", "black")
            Screen.set_color("white", "blue")
        """
        cls._foreground = COLOR_NAMES.get(foreground.lower(), Color.WHITE)
        cls._background = COLOR_NAMES.get(background.lower(), Color.BLACK)
        
        cls._operations.append({
            "type": "set_color",
            "foreground": cls._foreground.value,
            "background": cls._background.value,
        })
    
    @classmethod
    def set_cursor(cls, row: int, col: int) -> None:
        """
        Set the cursor position.
        
        Args:
            row: Row position (0-24)
            col: Column position (0-79)
        
        Example:
            Screen.set_cursor(10, 40)
        """
        cls._cursor_row = max(0, min(row, cls._config.height - 1))
        cls._cursor_col = max(0, min(col, cls._config.width - 1))
        
        cls._operations.append({
            "type": "set_cursor",
            "row": cls._cursor_row,
            "col": cls._cursor_col,
        })
    
    @classmethod
    def get_cursor(cls) -> Tuple[int, int]:
        """
        Get the current cursor position.
        
        Returns:
            Tuple of (row, col)
        """
        return (cls._cursor_row, cls._cursor_col)
    
    @classmethod
    def scroll_up(cls, lines: int = 1) -> None:
        """
        Scroll the screen up by a number of lines.
        
        Args:
            lines: Number of lines to scroll (default: 1)
        """
        cls._operations.append({
            "type": "scroll_up",
            "lines": lines,
        })
    
    @classmethod
    def scroll_down(cls, lines: int = 1) -> None:
        """
        Scroll the screen down by a number of lines.
        
        Args:
            lines: Number of lines to scroll (default: 1)
        """
        cls._operations.append({
            "type": "scroll_down",
            "lines": lines,
        })
    
    @classmethod
    def enable_cursor(cls) -> None:
        """Enable the hardware cursor."""
        cls._operations.append({"type": "enable_cursor"})
    
    @classmethod
    def disable_cursor(cls) -> None:
        """Disable the hardware cursor."""
        cls._operations.append({"type": "disable_cursor"})
    
    @classmethod
    def get_width(cls) -> int:
        """Get screen width in characters."""
        return cls._config.width
    
    @classmethod
    def get_height(cls) -> int:
        """Get screen height in characters."""
        return cls._config.height
    
    @classmethod
    def _reset(cls) -> None:
        """Reset screen state (used internally)."""
        cls._cursor_row = 0
        cls._cursor_col = 0
        cls._foreground = Color.WHITE
        cls._background = Color.BLACK
        cls._operations = []
    
    @classmethod
    def _get_operations(cls) -> list:
        """Get all recorded operations (used by compiler)."""
        return cls._operations.copy()
