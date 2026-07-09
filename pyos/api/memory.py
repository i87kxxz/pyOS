"""
pyOS Memory Manager — build-time recording bound to active Kernel heap config.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from .errors import UnsupportedOpError
from .kernel import get_active_kernel


class AllocationType(Enum):
    STATIC = "static"
    DYNAMIC = "dynamic"


@dataclass
class MemoryBlock:
    address: int
    size: int
    used: bool = False
    name: Optional[str] = None
    symbol: Optional[str] = None


@dataclass
class MemoryRegion:
    start: int
    end: int
    name: str
    writable: bool = True
    executable: bool = False


class Memory:
    KERNEL_START = 0x100000
    KERNEL_SIZE = 0x100000
    HEAP_START = 0x200000
    HEAP_SIZE = 0x100000  # overridden by bind_kernel
    STACK_TOP = 0x90000
    STACK_SIZE = 0x10000
    VGA_ADDRESS = 0xB8000

    _static_allocations: List[MemoryBlock] = []
    _heap_blocks: List[MemoryBlock] = []
    _next_static_address: int = KERNEL_START + KERNEL_SIZE
    _operations: list = []
    _symbol_counter: int = 0
    _kernel_ref = None

    @classmethod
    def bind_kernel(cls, kernel) -> None:
        cls._kernel_ref = kernel
        cls.HEAP_SIZE = kernel.config.heap_size
        cls.HEAP_START = kernel.config.heap_start
        cls.STACK_TOP = kernel.config.stack_top
        cls.STACK_SIZE = kernel.config.stack_size

    @classmethod
    def _next_symbol(cls, prefix: str = "mem") -> str:
        cls._symbol_counter += 1
        return f"{prefix}_{cls._symbol_counter}"

    @classmethod
    def allocate_static(cls, size: int, name: Optional[str] = None, align: int = 4) -> str:
        if size <= 0:
            raise ValueError("allocate_static size must be > 0")
        sym = name or cls._next_symbol("static")
        cls._operations.append(
            {"type": "allocate_static", "size": size, "name": name, "symbol": sym}
        )
        return sym

    @classmethod
    def malloc(cls, size: int) -> str:
        if size <= 0:
            raise ValueError("malloc size must be > 0")
        sym = cls._next_symbol("ptr")
        cls._operations.append({"type": "malloc", "size": size, "symbol": sym})
        return sym

    @classmethod
    def free(cls, symbol_or_addr) -> None:
        cls._operations.append({"type": "free", "symbol": str(symbol_or_addr)})

    @classmethod
    def realloc(cls, symbol: str, new_size: int) -> str:
        out = cls._next_symbol("ptr")
        cls._operations.append(
            {"type": "realloc", "symbol": str(symbol), "new_size": new_size, "out_symbol": out}
        )
        return out

    @classmethod
    def calloc(cls, count: int, size: int) -> str:
        sym = cls._next_symbol("ptr")
        cls._operations.append(
            {"type": "calloc", "count": count, "size": size, "symbol": sym}
        )
        return sym

    @classmethod
    def memset(cls, symbol: str, value: int, size: int) -> None:
        cls._operations.append(
            {"type": "memset", "symbol": str(symbol), "value": value & 0xFF, "size": size}
        )

    @classmethod
    def memcpy(cls, dest: str, src: str, size: int) -> None:
        cls._operations.append(
            {"type": "memcpy", "dest": str(dest), "src": str(src), "size": size}
        )

    @classmethod
    def read_byte(cls, symbol: str) -> None:
        raise UnsupportedOpError(
            "Memory.read_byte",
            "Raw peek/poke is not emitted; use memset/memcpy or C syscalls",
        )

    @classmethod
    def write_byte(cls, symbol: str, value: int) -> None:
        raise UnsupportedOpError("Memory.write_byte", "Use memset or C-side code")

    @classmethod
    def read_word(cls, symbol: str) -> None:
        raise UnsupportedOpError("Memory.read_word")

    @classmethod
    def write_word(cls, symbol: str, value: int) -> None:
        raise UnsupportedOpError("Memory.write_word")

    @classmethod
    def read_dword(cls, symbol: str) -> None:
        raise UnsupportedOpError("Memory.read_dword")

    @classmethod
    def write_dword(cls, symbol: str, value: int) -> None:
        raise UnsupportedOpError("Memory.write_dword")

    @classmethod
    def get_free_memory(cls) -> int:
        k = cls._kernel_ref or get_active_kernel()
        return k.config.heap_size if k else cls.HEAP_SIZE

    @classmethod
    def get_used_memory(cls) -> int:
        return 0

    @classmethod
    def get_memory_map(cls) -> List[MemoryRegion]:
        return [
            MemoryRegion(0x0, 0x500, "Real Mode IVT/BDA", writable=False),
            MemoryRegion(0x7C00, 0x7E00, "Bootloader", executable=True),
            MemoryRegion(cls.STACK_TOP - cls.STACK_SIZE, cls.STACK_TOP, "Stack"),
            MemoryRegion(cls.VGA_ADDRESS, cls.VGA_ADDRESS + 0x8000, "VGA Buffer"),
            MemoryRegion(cls.KERNEL_START, cls.KERNEL_START + cls.KERNEL_SIZE, "Kernel", executable=True),
            MemoryRegion(cls.HEAP_START, cls.HEAP_START + cls.HEAP_SIZE, "Heap"),
        ]

    @classmethod
    def _reset(cls) -> None:
        cls._static_allocations = []
        cls._heap_blocks = []
        cls._next_static_address = cls.KERNEL_START + cls.KERNEL_SIZE
        cls._operations = []
        # keep symbol counter monotonic across boot funcs in one generate()

    @classmethod
    def _reset_symbols(cls) -> None:
        cls._symbol_counter = 0

    @classmethod
    def _get_operations(cls) -> list:
        return cls._operations.copy()
