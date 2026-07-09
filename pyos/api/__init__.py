"""Public Python DSL for building pyOS kernels."""

from .errors import BuildTimeOnlyError, CapabilityError, UnsupportedOpError
from .gdt import GDT, GDTEntry, PrivilegeLevel, SegmentType
from .interrupts import InterruptFrame, InterruptType, Interrupts
from .kernel import Architecture, Kernel, KernelConfig
from .keyboard import KeyCode, KeyEvent, Keyboard
from .memory import Memory, MemoryBlock, MemoryRegion
from .screen import COLOR_NAMES, Color, Screen
from .syscalls import SysCall, SysCallContext, SysCallNumber

__all__ = [
    "Architecture",
    "BuildTimeOnlyError",
    "COLOR_NAMES",
    "CapabilityError",
    "Color",
    "GDT",
    "GDTEntry",
    "InterruptFrame",
    "InterruptType",
    "Interrupts",
    "Kernel",
    "KernelConfig",
    "KeyCode",
    "KeyEvent",
    "Keyboard",
    "Memory",
    "MemoryBlock",
    "MemoryRegion",
    "PrivilegeLevel",
    "Screen",
    "SegmentType",
    "SysCall",
    "SysCallContext",
    "SysCallNumber",
    "UnsupportedOpError",
]
