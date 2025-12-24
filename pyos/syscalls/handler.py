"""
pyOS System Call Handler
"""

from typing import Callable, Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum


class SysCallNumber(Enum):
    """Standard system call numbers"""
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


@dataclass
class SysCallContext:
    """Context passed to system call handlers"""
    syscall_number: int
    arg1: int = 0
    arg2: int = 0
    arg3: int = 0
    arg4: int = 0
    arg5: int = 0


class SysCall:
    """
    System Call Manager.
    
    Provides methods to define and handle system calls.
    
    Example:
        @SysCall.handler(SysCallNumber.SYS_WRITE)
        def sys_write(ctx):
            fd = ctx.arg1
            buf = ctx.arg2
            count = ctx.arg3
            # Write implementation
            return count
    """
    
    _handlers: Dict[int, Callable] = {}
    _operations: list = []
    
    @classmethod
    def handler(cls, syscall: SysCallNumber):
        """
        Decorator to register a system call handler.
        
        Args:
            syscall: The system call number
        
        Example:
            @SysCall.handler(SysCallNumber.SYS_EXIT)
            def sys_exit(ctx):
                # Exit implementation
                pass
        """
        def decorator(func: Callable) -> Callable:
            cls._handlers[syscall.value] = func
            cls._operations.append({
                "type": "register_handler",
                "syscall": syscall.value,
                "name": func.__name__,
            })
            return func
        return decorator
    
    @classmethod
    def register(cls, syscall_number: int, handler: Callable) -> None:
        """
        Register a system call handler by number.
        
        Args:
            syscall_number: System call number
            handler: Handler function
        
        Example:
            def my_syscall(ctx):
                return 0
            SysCall.register(100, my_syscall)
        """
        cls._handlers[syscall_number] = handler
        cls._operations.append({
            "type": "register_handler",
            "syscall": syscall_number,
            "name": handler.__name__,
        })
    
    @classmethod
    def call(cls, syscall_number: int, *args) -> int:
        """
        Invoke a system call.
        
        Args:
            syscall_number: System call number
            *args: Arguments to pass
        
        Returns:
            Return value from syscall.
        
        Example:
            result = SysCall.call(SysCallNumber.SYS_WRITE.value, 1, buffer, length)
        """
        cls._operations.append({
            "type": "call",
            "syscall": syscall_number,
            "args": args,
        })
        
        handler = cls._handlers.get(syscall_number)
        if handler:
            ctx = SysCallContext(
                syscall_number=syscall_number,
                arg1=args[0] if len(args) > 0 else 0,
                arg2=args[1] if len(args) > 1 else 0,
                arg3=args[2] if len(args) > 2 else 0,
                arg4=args[3] if len(args) > 3 else 0,
                arg5=args[4] if len(args) > 4 else 0,
            )
            return handler(ctx)
        return -1
    
    @classmethod
    def exit(cls, code: int = 0) -> None:
        """
        Exit the current process.
        
        Args:
            code: Exit code (default: 0)
        """
        cls._operations.append({
            "type": "exit",
            "code": code,
        })
    
    @classmethod
    def sleep(cls, milliseconds: int) -> None:
        """
        Sleep for specified milliseconds.
        
        Args:
            milliseconds: Time to sleep
        """
        cls._operations.append({
            "type": "sleep",
            "ms": milliseconds,
        })
    
    @classmethod
    def get_time(cls) -> int:
        """
        Get current system time.
        
        Returns:
            Time in milliseconds since boot.
        """
        cls._operations.append({"type": "get_time"})
        return 0
    
    @classmethod
    def _reset(cls) -> None:
        """Reset syscall state (used internally)."""
        cls._handlers = {}
        cls._operations = []
    
    @classmethod
    def _get_operations(cls) -> list:
        """Get all recorded operations (used by compiler)."""
        return cls._operations.copy()
