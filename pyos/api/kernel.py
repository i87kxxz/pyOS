"""
pyOS Kernel — Python DSL that builds a real freestanding C kernel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .errors import CapabilityError, UnsupportedOpError


class Architecture(Enum):
    X86 = "x86"
    X86_64 = "x86_64"


@dataclass
class KernelConfig:
    arch: Architecture = Architecture.X86
    stack_size: int = 16384
    heap_size: int = 1048576
    heap_start: int = 0x200000
    stack_top: int = 0x90000
    video_mode: str = "text"
    enable_interrupts: bool = True
    enable_gdt: bool = True
    enable_paging: bool = False
    enable_user_mode: bool = False
    enable_processes: bool = False
    enable_filesystem: bool = False
    debug_level: str = "lab"  # quiet | lab
    keypress_mode: str = "echo"  # echo | custom


@dataclass
class KernelFunction:
    name: str
    func: Callable
    event: str
    priority: int = 0
    key_filter: Optional[str] = None
    interval_ms: int = 1000


# Active kernel for Memory/Screen/Process/File binding during boot recording
_ACTIVE_KERNEL: Optional["Kernel"] = None


def get_active_kernel() -> Optional["Kernel"]:
    return _ACTIVE_KERNEL


class Kernel:
    """
    Build-time OS definition. Boot handlers run on the host to record ops;
    the C kernel executes the generated glue at runtime.
    """

    def __init__(
        self,
        arch: str = "x86",
        stack_size: int = 16384,
        heap_size: int = 1048576,
        enable_interrupts: bool = True,
        enable_gdt: bool = True,
        enable_paging: bool = False,
        enable_user_mode: bool = False,
        enable_processes: bool = False,
        enable_filesystem: bool = False,
        debug_level: str = "lab",
        keypress_mode: str = "echo",
    ):
        if arch != "x86":
            raise ValueError(
                "Only arch='x86' is supported.\n"
                "  Why: the C kernel and bootloader are 32-bit protected mode.\n"
                "  Hint: use Kernel(arch='x86')"
            )
        if debug_level not in ("quiet", "lab"):
            raise ValueError("debug_level must be 'quiet' or 'lab'")
        if keypress_mode not in ("echo", "custom"):
            raise ValueError("keypress_mode must be 'echo' or 'custom'")

        # stack grows down from stack_top; keep classic low-memory top
        stack_top = 0x90000
        if stack_size < 4096 or stack_size > 0x80000:
            raise ValueError("stack_size must be between 4096 and 524288")

        self.config = KernelConfig(
            arch=Architecture(arch),
            stack_size=stack_size,
            heap_size=heap_size,
            stack_top=stack_top,
            enable_interrupts=enable_interrupts,
            enable_gdt=enable_gdt,
            enable_paging=enable_paging,
            enable_user_mode=enable_user_mode,
            enable_processes=enable_processes,
            enable_filesystem=enable_filesystem,
            debug_level=debug_level,
            keypress_mode=keypress_mode,
        )

        self.capabilities: Dict[str, bool] = {
            "screen_text": True,
            "heap_alloc": True,
            "heap_free": True,
            "keyboard_irq": True,
            "timer": True,
            "syscalls": True,
            "paging": enable_paging,
            "user_mode": enable_user_mode,
            "processes": enable_processes,
            "filesystem": enable_filesystem,
            "gdt_runtime": enable_gdt,
        }

        self._boot_functions: List[KernelFunction] = []
        self._interrupt_handlers: Dict[int, KernelFunction] = {}
        self._syscall_handlers: Dict[int, KernelFunction] = {}
        self._keypress_handlers: List[KernelFunction] = []
        self._timer_handlers: List[KernelFunction] = []
        self._custom_handlers: Dict[str, List[KernelFunction]] = {}
        self._compiled_asm: Optional[str] = None
        self._compiled_binary: Optional[bytes] = None
        self._seed_files: Dict[str, bytes] = {}

        from .fs import File
        from .memory import Memory
        from .process import Process

        Memory.bind_kernel(self)
        Process.bind_kernel(self)
        File.bind_kernel(self)

    def require_capability(self, name: str, hint: str = "") -> None:
        if not self.capabilities.get(name):
            raise CapabilityError(name, hint or f"Pass the matching Kernel(...) flag to enable '{name}'")

    def on_boot(self, func: Callable = None, *, priority: int = 0):
        def decorator(f: Callable) -> Callable:
            self._boot_functions.append(
                KernelFunction(name=f.__name__, func=f, event="boot", priority=priority)
            )
            self._boot_functions.sort(key=lambda x: x.priority)
            return f

        if func is not None:
            return decorator(func)
        return decorator

    def on_keypress(self, func: Callable = None, *, key: str = None, mode: str = None):
        def decorator(f: Callable) -> Callable:
            handler = KernelFunction(name=f.__name__, func=f, event="keypress")
            handler.key_filter = key
            self._keypress_handlers.append(handler)
            if mode:
                self.config.keypress_mode = mode
            return f

        if func is not None:
            return decorator(func)
        return decorator

    def on_interrupt(self, interrupt_number: int):
        def decorator(func: Callable) -> Callable:
            raise UnsupportedOpError(
                f"on_interrupt({interrupt_number})",
                "Custom IRQ handlers are reserved; use @on_keypress / @on_timer / built-in IDT",
            )

        return decorator

    def on_syscall(self, syscall_number: int):
        def decorator(func: Callable) -> Callable:
            raise UnsupportedOpError(
                f"on_syscall({syscall_number})",
                "Syscall table is fixed in C (see SysCallNumber). Extend the C dispatcher to add numbers.",
            )

        return decorator

    def on_timer(self, interval_ms: int = 1000):
        def decorator(func: Callable) -> Callable:
            self.require_capability("timer", "Timer requires enable_interrupts=True")
            if not self.config.enable_interrupts:
                raise CapabilityError("timer", "Set enable_interrupts=True")
            handler = KernelFunction(name=func.__name__, func=func, event="timer")
            handler.interval_ms = max(10, int(interval_ms))
            self._timer_handlers.append(handler)
            return func

        return decorator

    def on_event(self, event_name: str):
        def decorator(func: Callable) -> Callable:
            raise UnsupportedOpError(
                f"on_event({event_name!r})",
                "Custom event bus is not part of the C kernel; use on_boot/on_timer/on_keypress",
            )

        return decorator

    def seed_file(self, path: str, data) -> None:
        self.require_capability("filesystem")
        if isinstance(data, str):
            data = data.encode("ascii", errors="replace")
        self._seed_files[path.lstrip("/")] = data

    def compile(self) -> str:
        global _ACTIVE_KERNEL
        from ..build.codegen import CodeGenerator

        _ACTIVE_KERNEL = self
        try:
            generator = CodeGenerator(self)
            self._compiled_asm = generator.generate()
            return self._compiled_asm
        finally:
            _ACTIVE_KERNEL = None

    def assemble(self) -> bytes:
        from pathlib import Path
        import tempfile

        from ..build.builder import OSBuilder

        builder = OSBuilder(self)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kernel.bin"
            builder.build_bin(str(path))
            self._compiled_binary = path.read_bytes()
        return self._compiled_binary

    def build(self, output: str, format: str = "bin") -> str:
        from ..build.builder import OSBuilder

        builder = OSBuilder(self)
        if format == "iso":
            return builder.build_iso(output)
        if format == "bin":
            return builder.build_bin(output)
        raise ValueError(f"Unknown format: {format}")

    def run(self, image_path: str = None, debug: bool = False):
        from ..emulator import QEMURunner

        if image_path is None:
            image_path = self.build("temp_os.bin")
        runner = QEMURunner(self.config.arch)
        runner.run(image_path, debug=debug)

    def get_info(self) -> Dict[str, Any]:
        return {
            "architecture": self.config.arch.value,
            "stack_size": self.config.stack_size,
            "stack_top": self.config.stack_top,
            "heap_size": self.config.heap_size,
            "interrupts_enabled": self.config.enable_interrupts,
            "gdt_enabled": self.config.enable_gdt,
            "paging": self.config.enable_paging,
            "user_mode": self.config.enable_user_mode,
            "processes": self.config.enable_processes,
            "filesystem": self.config.enable_filesystem,
            "boot_functions": len(self._boot_functions),
            "keypress_handlers": len(self._keypress_handlers),
            "timer_handlers": len(self._timer_handlers),
            "capabilities": dict(self.capabilities),
        }
