"""
pyOS Keyboard Driver - PS/2 Keyboard Support
"""

from typing import Optional, Callable, Dict
from enum import Enum
from dataclasses import dataclass


class KeyCode(Enum):
    """Keyboard scan codes"""
    ESC = 0x01
    KEY_1 = 0x02
    KEY_2 = 0x03
    KEY_3 = 0x04
    KEY_4 = 0x05
    KEY_5 = 0x06
    KEY_6 = 0x07
    KEY_7 = 0x08
    KEY_8 = 0x09
    KEY_9 = 0x0A
    KEY_0 = 0x0B
    MINUS = 0x0C
    EQUALS = 0x0D
    BACKSPACE = 0x0E
    TAB = 0x0F
    KEY_Q = 0x10
    KEY_W = 0x11
    KEY_E = 0x12
    KEY_R = 0x13
    KEY_T = 0x14
    KEY_Y = 0x15
    KEY_U = 0x16
    KEY_I = 0x17
    KEY_O = 0x18
    KEY_P = 0x19
    LEFT_BRACKET = 0x1A
    RIGHT_BRACKET = 0x1B
    ENTER = 0x1C
    LEFT_CTRL = 0x1D
    KEY_A = 0x1E
    KEY_S = 0x1F
    KEY_D = 0x20
    KEY_F = 0x21
    KEY_G = 0x22
    KEY_H = 0x23
    KEY_J = 0x24
    KEY_K = 0x25
    KEY_L = 0x26
    SEMICOLON = 0x27
    QUOTE = 0x28
    BACKTICK = 0x29
    LEFT_SHIFT = 0x2A
    BACKSLASH = 0x2B
    KEY_Z = 0x2C
    KEY_X = 0x2D
    KEY_C = 0x2E
    KEY_V = 0x2F
    KEY_B = 0x30
    KEY_N = 0x31
    KEY_M = 0x32
    COMMA = 0x33
    PERIOD = 0x34
    SLASH = 0x35
    RIGHT_SHIFT = 0x36
    KEYPAD_STAR = 0x37
    LEFT_ALT = 0x38
    SPACE = 0x39
    CAPS_LOCK = 0x3A
    F1 = 0x3B
    F2 = 0x3C
    F3 = 0x3D
    F4 = 0x3E
    F5 = 0x3F
    F6 = 0x40
    F7 = 0x41
    F8 = 0x42
    F9 = 0x43
    F10 = 0x44
    F11 = 0x57
    F12 = 0x58
    UP = 0x48
    DOWN = 0x50
    LEFT = 0x4B
    RIGHT = 0x4D


# Scancode to character mapping (US layout)
SCANCODE_TO_CHAR: Dict[int, str] = {
    0x02: '1', 0x03: '2', 0x04: '3', 0x05: '4', 0x06: '5',
    0x07: '6', 0x08: '7', 0x09: '8', 0x0A: '9', 0x0B: '0',
    0x0C: '-', 0x0D: '=',
    0x10: 'q', 0x11: 'w', 0x12: 'e', 0x13: 'r', 0x14: 't',
    0x15: 'y', 0x16: 'u', 0x17: 'i', 0x18: 'o', 0x19: 'p',
    0x1A: '[', 0x1B: ']',
    0x1E: 'a', 0x1F: 's', 0x20: 'd', 0x21: 'f', 0x22: 'g',
    0x23: 'h', 0x24: 'j', 0x25: 'k', 0x26: 'l',
    0x27: ';', 0x28: "'", 0x29: '`',
    0x2B: '\\',
    0x2C: 'z', 0x2D: 'x', 0x2E: 'c', 0x2F: 'v', 0x30: 'b',
    0x31: 'n', 0x32: 'm',
    0x33: ',', 0x34: '.', 0x35: '/',
    0x39: ' ',
}

SCANCODE_TO_CHAR_SHIFT: Dict[int, str] = {
    0x02: '!', 0x03: '@', 0x04: '#', 0x05: '$', 0x06: '%',
    0x07: '^', 0x08: '&', 0x09: '*', 0x0A: '(', 0x0B: ')',
    0x0C: '_', 0x0D: '+',
    0x10: 'Q', 0x11: 'W', 0x12: 'E', 0x13: 'R', 0x14: 'T',
    0x15: 'Y', 0x16: 'U', 0x17: 'I', 0x18: 'O', 0x19: 'P',
    0x1A: '{', 0x1B: '}',
    0x1E: 'A', 0x1F: 'S', 0x20: 'D', 0x21: 'F', 0x22: 'G',
    0x23: 'H', 0x24: 'J', 0x25: 'K', 0x26: 'L',
    0x27: ':', 0x28: '"', 0x29: '~',
    0x2B: '|',
    0x2C: 'Z', 0x2D: 'X', 0x2E: 'C', 0x2F: 'V', 0x30: 'B',
    0x31: 'N', 0x32: 'M',
    0x33: '<', 0x34: '>', 0x35: '?',
    0x39: ' ',
}


@dataclass
class KeyEvent:
    """Represents a keyboard event"""
    scancode: int
    char: str
    pressed: bool  # True for key down, False for key up
    shift: bool
    ctrl: bool
    alt: bool


class Keyboard:
    """
    PS/2 Keyboard Driver.
    
    Provides methods to read keyboard input.
    
    Example:
        @kernel.on_keypress
        def handle_key(key):
            Screen.print(f"You pressed: {key.char}")
    """
    
    _handlers: list = []
    _buffer: list = []
    _shift_pressed: bool = False
    _ctrl_pressed: bool = False
    _alt_pressed: bool = False
    _operations: list = []
    
    @classmethod
    def read_key(cls) -> Optional[KeyEvent]:
        """
        Read a single key from the keyboard buffer.
        
        Returns:
            KeyEvent if a key is available, None otherwise.
        
        Example:
            key = Keyboard.read_key()
            if key:
                Screen.print(key.char)
        """
        cls._operations.append({"type": "read_key"})
        if cls._buffer:
            return cls._buffer.pop(0)
        return None
    
    @classmethod
    def read_char(cls) -> Optional[str]:
        """
        Read a single character from keyboard.
        
        Returns:
            Character string if available, None otherwise.
        
        Example:
            char = Keyboard.read_char()
        """
        cls._operations.append({"type": "read_char"})
        key = cls.read_key()
        if key and key.char:
            return key.char
        return None
    
    @classmethod
    def read_line(cls) -> str:
        """
        Read a line of input (until Enter is pressed).
        
        Returns:
            The input string.
        
        Example:
            name = Keyboard.read_line()
            Screen.print(f"Hello, {name}!")
        """
        cls._operations.append({"type": "read_line"})
        return ""  # Placeholder - actual implementation in ASM
    
    @classmethod
    def wait_key(cls) -> KeyEvent:
        """
        Wait for a key press (blocking).
        
        Returns:
            The KeyEvent when a key is pressed.
        
        Example:
            Screen.print("Press any key...")
            key = Keyboard.wait_key()
        """
        cls._operations.append({"type": "wait_key"})
        return KeyEvent(0, '', True, False, False, False)
    
    @classmethod
    def is_key_pressed(cls, key: KeyCode) -> bool:
        """
        Check if a specific key is currently pressed.
        
        Args:
            key: The KeyCode to check
        
        Returns:
            True if the key is pressed.
        
        Example:
            if Keyboard.is_key_pressed(KeyCode.SPACE):
                Screen.print("Space is pressed!")
        """
        cls._operations.append({
            "type": "is_key_pressed",
            "keycode": key.value,
        })
        return False
    
    @classmethod
    def is_shift_pressed(cls) -> bool:
        """Check if Shift key is pressed."""
        return cls._shift_pressed
    
    @classmethod
    def is_ctrl_pressed(cls) -> bool:
        """Check if Ctrl key is pressed."""
        return cls._ctrl_pressed
    
    @classmethod
    def is_alt_pressed(cls) -> bool:
        """Check if Alt key is pressed."""
        return cls._alt_pressed
    
    @classmethod
    def clear_buffer(cls) -> None:
        """Clear the keyboard buffer."""
        cls._buffer.clear()
        cls._operations.append({"type": "clear_buffer"})
    
    @classmethod
    def set_repeat_rate(cls, delay_ms: int = 500, rate_cps: int = 10) -> None:
        """
        Set keyboard repeat rate.
        
        Args:
            delay_ms: Delay before repeat starts (ms)
            rate_cps: Characters per second when repeating
        """
        cls._operations.append({
            "type": "set_repeat_rate",
            "delay": delay_ms,
            "rate": rate_cps,
        })
    
    @classmethod
    def _process_scancode(cls, scancode: int) -> Optional[KeyEvent]:
        """Process a raw scancode (used internally)."""
        pressed = (scancode & 0x80) == 0
        code = scancode & 0x7F
        
        # Handle modifier keys
        if code == KeyCode.LEFT_SHIFT.value or code == KeyCode.RIGHT_SHIFT.value:
            cls._shift_pressed = pressed
            return None
        elif code == KeyCode.LEFT_CTRL.value:
            cls._ctrl_pressed = pressed
            return None
        elif code == KeyCode.LEFT_ALT.value:
            cls._alt_pressed = pressed
            return None
        
        # Get character
        char_map = SCANCODE_TO_CHAR_SHIFT if cls._shift_pressed else SCANCODE_TO_CHAR
        char = char_map.get(code, '')
        
        return KeyEvent(
            scancode=code,
            char=char,
            pressed=pressed,
            shift=cls._shift_pressed,
            ctrl=cls._ctrl_pressed,
            alt=cls._alt_pressed,
        )
    
    @classmethod
    def _reset(cls) -> None:
        """Reset keyboard state (used internally)."""
        cls._handlers = []
        cls._buffer = []
        cls._shift_pressed = False
        cls._ctrl_pressed = False
        cls._alt_pressed = False
        cls._operations = []
    
    @classmethod
    def _get_operations(cls) -> list:
        """Get all recorded operations (used by compiler)."""
        return cls._operations.copy()
