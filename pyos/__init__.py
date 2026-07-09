"""
pyOS - Build real operating systems with a Python DSL
"""

from .api import (
    GDT,
    Architecture,
    BuildTimeOnlyError,
    COLOR_NAMES,
    CapabilityError,
    Color,
    InterruptType,
    Interrupts,
    Kernel,
    KernelConfig,
    KeyCode,
    KeyEvent,
    Keyboard,
    Memory,
    Screen,
    SysCall,
    SysCallNumber,
    UnsupportedOpError,
)
from .api.fs import File
from .api.process import Process

__version__ = "1.0.0"
__all__ = [
    "Architecture",
    "BuildTimeOnlyError",
    "COLOR_NAMES",
    "CapabilityError",
    "Color",
    "File",
    "GDT",
    "InterruptType",
    "Interrupts",
    "Kernel",
    "KernelConfig",
    "KeyCode",
    "KeyEvent",
    "Keyboard",
    "Memory",
    "Process",
    "Screen",
    "SysCall",
    "SysCallNumber",
    "UnsupportedOpError",
]
