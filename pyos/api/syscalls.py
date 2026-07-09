"""
pyOS System Call numbers — must stay in sync with kernel/include/syscall.h
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict

from .errors import UnsupportedOpError


class SysCallNumber(Enum):
    SYS_EXIT = 1
    SYS_READ = 3
    SYS_WRITE = 4
    SYS_OPEN = 5
    SYS_CLOSE = 6
    SYS_GETPID = 20
    SYS_MALLOC = 90
    SYS_FREE = 91
    SYS_SLEEP = 162
    SYS_TIME = 201
    SYS_YIELD = 158
    SYS_SPAWN = 2


@dataclass
class SysCallContext:
    syscall_number: int
    arg1: int = 0
    arg2: int = 0
    arg3: int = 0
    arg4: int = 0
    arg5: int = 0


class SysCall:
    _handlers: Dict[int, Callable] = {}
    _operations: list = []

    @classmethod
    def handler(cls, syscall: SysCallNumber):
        def decorator(func: Callable) -> Callable:
            raise UnsupportedOpError(
                f"SysCall.handler({syscall.name})",
                "Handlers are implemented in C syscall_dispatch; Python cannot replace them",
            )

        return decorator

    @classmethod
    def register(cls, syscall_number: int, handler: Callable) -> None:
        raise UnsupportedOpError("SysCall.register", "Fixed C syscall table only")

    @classmethod
    def call(cls, syscall_number: int, *args) -> None:
        cls._operations.append(
            {"type": "syscall_call", "syscall": int(syscall_number), "args": list(args)}
        )

    @classmethod
    def exit(cls, code: int = 0) -> None:
        cls._operations.append({"type": "syscall_exit", "code": int(code)})

    @classmethod
    def sleep(cls, milliseconds: int) -> None:
        cls._operations.append({"type": "syscall_sleep", "ms": int(milliseconds)})

    @classmethod
    def get_time(cls) -> None:
        cls._operations.append({"type": "syscall_time"})

    @classmethod
    def _reset(cls) -> None:
        cls._handlers = {}
        cls._operations = []

    @classmethod
    def _get_operations(cls) -> list:
        return cls._operations.copy()
