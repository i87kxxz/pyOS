"""
pyOS System Call numbers — must stay in sync with kernel/include/syscall.h

Default numbers match Linux i386 (syscall_32.tbl).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict

from .errors import UnsupportedOpError


class SysCallNumber(Enum):
    # Linux i386
    SYS_EXIT = 1
    SYS_FORK = 2
    SYS_READ = 3
    SYS_WRITE = 4
    SYS_OPEN = 5
    SYS_CLOSE = 6
    SYS_WAITPID = 7
    SYS_EXECVE = 11
    SYS_CHDIR = 12
    SYS_TIME = 13
    SYS_GETPID = 20
    SYS_GETUID = 24
    SYS_DUP = 41
    SYS_PIPE = 42
    SYS_BRK = 45
    SYS_GETGID = 47
    SYS_IOCTL = 54
    SYS_FCNTL = 55
    SYS_DUP2 = 63
    SYS_SELECT = 82
    SYS_MMAP = 90
    SYS_MUNMAP = 91
    SYS_SOCKETCALL = 102
    SYS_STAT = 106
    SYS_LSTAT = 107
    SYS_FSTAT = 108
    SYS_UNAME = 109
    SYS_WAIT4 = 114
    SYS_MPROTECT = 125
    SYS_SCHED_YIELD = 158
    SYS_NANOSLEEP = 162
    SYS_POLL = 168
    SYS_RT_SIGACTION = 174
    SYS_RT_SIGPROCMASK = 175
    SYS_GETCWD = 183
    SYS_MMAP2 = 192
    SYS_GETDENTS = 141
    SYS_GETDENTS64 = 220
    SYS_SET_THREAD_AREA = 243
    SYS_EXIT_GROUP = 252
    SYS_ACCESS = 33
    SYS_GETEUID = 49
    SYS_GETEGID = 50
    SYS_GETPPID = 64
    SYS_UGETRLIMIT = 191
    SYS_OPENAT = 295
    SYS_FACCESSAT = 307

    # DSL aliases (same values as Linux counterparts)
    SYS_YIELD = 158
    SYS_SLEEP = 162

    # Non-Linux pyOS extensions
    PYOS_SYS_MALLOC = 0x70000001
    PYOS_SYS_FREE = 0x70000002
    PYOS_SYS_SPAWN = 0x70000003


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
