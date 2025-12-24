"""
pyOS Kernel - The core of your operating system
"""

from typing import Callable, Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class Architecture(Enum):
    X86 = "x86"
    X86_64 = "x86_64"


@dataclass
class KernelConfig:
    """Configuration for the kernel"""
    arch: Architecture = Architecture.X86
    stack_size: int = 16384  # 16KB stack
    heap_size: int = 1048576  # 1MB heap
    video_mode: str = "text"  # text or graphics
    enable_interrupts: bool = True
    enable_gdt: bool = True
    enable_paging: bool = False


@dataclass
class KernelFunction:
    """Represents a registered kernel function"""
    name: str
    func: Callable
    event: str
    priority: int = 0


class Kernel:
    """
    The main Kernel class for building operating systems.
    
    Example:
        kernel = Kernel(arch="x86")
        
        @kernel.on_boot
        def main():
            Screen.print("Hello from MyOS!")
        
        kernel.build("myos.iso")
    """
    
    def __init__(
        self,
        arch: str = "x86",
        stack_size: int = 16384,
        heap_size: int = 1048576,
        enable_interrupts: bool = True,
        enable_gdt: bool = True,
    ):
        """
        Initialize a new Kernel.
        
        Args:
            arch: Target architecture ("x86" or "x86_64")
            stack_size: Stack size in bytes (default 16KB)
            heap_size: Heap size in bytes (default 1MB)
            enable_interrupts: Enable interrupt handling
            enable_gdt: Enable Global Descriptor Table
        """
        self.config = KernelConfig(
            arch=Architecture(arch),
            stack_size=stack_size,
            heap_size=heap_size,
            enable_interrupts=enable_interrupts,
            enable_gdt=enable_gdt,
        )
        
        self._boot_functions: List[KernelFunction] = []
        self._interrupt_handlers: Dict[int, KernelFunction] = {}
        self._syscall_handlers: Dict[int, KernelFunction] = {}
        self._keypress_handlers: List[KernelFunction] = []
        self._timer_handlers: List[KernelFunction] = []
        self._custom_handlers: Dict[str, List[KernelFunction]] = {}
        
        self._compiled_asm: Optional[str] = None
        self._compiled_binary: Optional[bytes] = None
    
    def on_boot(self, func: Callable = None, *, priority: int = 0):
        """
        Decorator to register a function to run at boot.
        
        Example:
            @kernel.on_boot
            def start():
                Screen.print("Booting...")
        """
        def decorator(f: Callable) -> Callable:
            self._boot_functions.append(KernelFunction(
                name=f.__name__,
                func=f,
                event="boot",
                priority=priority,
            ))
            # Sort by priority (higher first)
            self._boot_functions.sort(key=lambda x: -x.priority)
            return f
        
        if func is not None:
            return decorator(func)
        return decorator
    
    def on_keypress(self, func: Callable = None, *, key: str = None):
        """
        Decorator to handle keyboard input.
        
        Example:
            @kernel.on_keypress
            def handle_key(key):
                Screen.print(f"Pressed: {key}")
        """
        def decorator(f: Callable) -> Callable:
            self._keypress_handlers.append(KernelFunction(
                name=f.__name__,
                func=f,
                event="keypress",
            ))
            return f
        
        if func is not None:
            return decorator(func)
        return decorator
    
    def on_interrupt(self, interrupt_number: int):
        """
        Decorator to handle a specific interrupt.
        
        Example:
            @kernel.on_interrupt(0x21)  # Keyboard interrupt
            def keyboard_handler():
                pass
        """
        def decorator(func: Callable) -> Callable:
            self._interrupt_handlers[interrupt_number] = KernelFunction(
                name=func.__name__,
                func=func,
                event=f"interrupt_{interrupt_number}",
            )
            return func
        return decorator
    
    def on_syscall(self, syscall_number: int):
        """
        Decorator to register a system call handler.
        
        Example:
            @kernel.on_syscall(1)  # sys_write
            def sys_write(fd, buf, count):
                pass
        """
        def decorator(func: Callable) -> Callable:
            self._syscall_handlers[syscall_number] = KernelFunction(
                name=func.__name__,
                func=func,
                event=f"syscall_{syscall_number}",
            )
            return func
        return decorator
    
    def on_timer(self, interval_ms: int = 1000):
        """
        Decorator to register a timer handler.
        
        Example:
            @kernel.on_timer(interval_ms=1000)
            def every_second():
                pass
        """
        def decorator(func: Callable) -> Callable:
            handler = KernelFunction(
                name=func.__name__,
                func=func,
                event="timer",
            )
            handler.interval_ms = interval_ms
            self._timer_handlers.append(handler)
            return func
        return decorator
    
    def on_event(self, event_name: str):
        """
        Decorator to register a custom event handler.
        
        Example:
            @kernel.on_event("custom_event")
            def handle_custom():
                pass
        """
        def decorator(func: Callable) -> Callable:
            if event_name not in self._custom_handlers:
                self._custom_handlers[event_name] = []
            self._custom_handlers[event_name].append(KernelFunction(
                name=func.__name__,
                func=func,
                event=event_name,
            ))
            return func
        return decorator
    
    def compile(self) -> str:
        """
        Compile the kernel to Assembly code.
        
        Returns:
            The generated Assembly code as a string.
        """
        from .compiler.codegen import CodeGenerator
        
        generator = CodeGenerator(self)
        self._compiled_asm = generator.generate()
        return self._compiled_asm
    
    def assemble(self) -> bytes:
        """
        Assemble the kernel to machine code.
        
        Returns:
            The binary machine code.
        """
        if self._compiled_asm is None:
            self.compile()
        
        from .compiler.assembler import Assembler
        
        assembler = Assembler(self.config.arch)
        self._compiled_binary = assembler.assemble(self._compiled_asm)
        return self._compiled_binary
    
    def build(self, output: str, format: str = "iso") -> str:
        """
        Build the complete OS image.
        
        Args:
            output: Output file path
            format: Output format ("iso" or "bin")
        
        Returns:
            Path to the generated file.
        """
        from .builder import OSBuilder
        
        if self._compiled_binary is None:
            self.assemble()
        
        builder = OSBuilder(self)
        
        if format == "iso":
            return builder.build_iso(output)
        elif format == "bin":
            return builder.build_bin(output)
        else:
            raise ValueError(f"Unknown format: {format}")
    
    def run(self, image_path: str = None, debug: bool = False):
        """
        Run the OS in QEMU.
        
        Args:
            image_path: Path to the OS image (builds if None)
            debug: Enable QEMU debug mode
        """
        from .emulator import QEMURunner
        
        if image_path is None:
            image_path = self.build("temp_os.iso")
        
        runner = QEMURunner(self.config.arch)
        runner.run(image_path, debug=debug)
    
    def get_info(self) -> Dict[str, Any]:
        """Get information about the kernel configuration."""
        return {
            "architecture": self.config.arch.value,
            "stack_size": self.config.stack_size,
            "heap_size": self.config.heap_size,
            "interrupts_enabled": self.config.enable_interrupts,
            "gdt_enabled": self.config.enable_gdt,
            "boot_functions": len(self._boot_functions),
            "interrupt_handlers": len(self._interrupt_handlers),
            "syscall_handlers": len(self._syscall_handlers),
        }
