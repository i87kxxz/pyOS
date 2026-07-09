"""
pyOS Interrupt Handler
"""

from typing import Callable, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class InterruptType(Enum):
    """Common interrupt types"""
    # CPU Exceptions (0-31)
    DIVIDE_ERROR = 0
    DEBUG = 1
    NMI = 2
    BREAKPOINT = 3
    OVERFLOW = 4
    BOUND_RANGE = 5
    INVALID_OPCODE = 6
    DEVICE_NOT_AVAILABLE = 7
    DOUBLE_FAULT = 8
    COPROCESSOR_SEGMENT = 9
    INVALID_TSS = 10
    SEGMENT_NOT_PRESENT = 11
    STACK_FAULT = 12
    GENERAL_PROTECTION = 13
    PAGE_FAULT = 14
    X87_FPU_ERROR = 16
    ALIGNMENT_CHECK = 17
    MACHINE_CHECK = 18
    SIMD_FPU_ERROR = 19
    
    # Hardware IRQs (32-47)
    IRQ_TIMER = 32          # IRQ0 - PIT Timer
    IRQ_KEYBOARD = 33       # IRQ1 - Keyboard
    IRQ_CASCADE = 34        # IRQ2 - Cascade
    IRQ_COM2 = 35           # IRQ3 - COM2
    IRQ_COM1 = 36           # IRQ4 - COM1
    IRQ_LPT2 = 37           # IRQ5 - LPT2
    IRQ_FLOPPY = 38         # IRQ6 - Floppy
    IRQ_LPT1 = 39           # IRQ7 - LPT1
    IRQ_RTC = 40            # IRQ8 - RTC
    IRQ_FREE1 = 41          # IRQ9
    IRQ_FREE2 = 42          # IRQ10
    IRQ_FREE3 = 43          # IRQ11
    IRQ_MOUSE = 44          # IRQ12 - PS/2 Mouse
    IRQ_FPU = 45            # IRQ13 - FPU
    IRQ_PRIMARY_ATA = 46    # IRQ14 - Primary ATA
    IRQ_SECONDARY_ATA = 47  # IRQ15 - Secondary ATA
    
    # System Call
    SYSCALL = 0x80


@dataclass
class InterruptFrame:
    """CPU state when interrupt occurred"""
    eip: int = 0
    cs: int = 0
    eflags: int = 0
    esp: int = 0
    ss: int = 0
    error_code: int = 0
    interrupt_number: int = 0


class Interrupts:
    """
    Interrupt Handler Manager.
    
    Provides methods to register and handle interrupts.
    
    Example:
        @Interrupts.handler(InterruptType.IRQ_KEYBOARD)
        def keyboard_handler(frame):
            key = Keyboard.read_key()
            Screen.print(f"Key: {key}")
    """
    
    _handlers: Dict[int, Callable] = {}
    _enabled: bool = False
    _operations: list = []
    
    @classmethod
    def handler(cls, interrupt: InterruptType):
        """
        Decorator to register an interrupt handler.
        
        Args:
            interrupt: The interrupt type to handle
        
        Example:
            @Interrupts.handler(InterruptType.IRQ_TIMER)
            def timer_handler(frame):
                pass
        """
        def decorator(func: Callable) -> Callable:
            cls._handlers[interrupt.value] = func
            cls._operations.append({
                "type": "register_handler",
                "interrupt": interrupt.value,
                "name": func.__name__,
            })
            return func
        return decorator
    
    @classmethod
    def register(cls, interrupt_number: int, handler: Callable) -> None:
        """
        Register an interrupt handler by number.
        
        Args:
            interrupt_number: Interrupt number (0-255)
            handler: Handler function
        
        Example:
            def my_handler(frame):
                pass
            Interrupts.register(33, my_handler)  # IRQ1 keyboard
        """
        cls._handlers[interrupt_number] = handler
        cls._operations.append({
            "type": "register_handler",
            "interrupt": interrupt_number,
            "name": handler.__name__,
        })
    
    @classmethod
    def unregister(cls, interrupt_number: int) -> None:
        """
        Unregister an interrupt handler.
        
        Args:
            interrupt_number: Interrupt number to unregister
        """
        if interrupt_number in cls._handlers:
            del cls._handlers[interrupt_number]
        cls._operations.append({
            "type": "unregister_handler",
            "interrupt": interrupt_number,
        })
    
    @classmethod
    def enable(cls) -> None:
        """
        Enable interrupts (STI instruction).
        
        Example:
            Interrupts.enable()
        """
        cls._enabled = True
        cls._operations.append({"type": "enable"})
    
    @classmethod
    def disable(cls) -> None:
        """
        Disable interrupts (CLI instruction).
        
        Example:
            Interrupts.disable()
        """
        cls._enabled = False
        cls._operations.append({"type": "disable"})
    
    @classmethod
    def is_enabled(cls) -> bool:
        """Check if interrupts are enabled."""
        return cls._enabled
    
    @classmethod
    def send_eoi(cls, irq: int) -> None:
        """
        Send End of Interrupt to PIC.
        
        Args:
            irq: IRQ number (0-15)
        """
        cls._operations.append({
            "type": "send_eoi",
            "irq": irq,
        })
    
    @classmethod
    def mask_irq(cls, irq: int) -> None:
        """
        Mask (disable) a specific IRQ.
        
        Args:
            irq: IRQ number (0-15)
        """
        cls._operations.append({
            "type": "mask_irq",
            "irq": irq,
        })
    
    @classmethod
    def unmask_irq(cls, irq: int) -> None:
        """
        Unmask (enable) a specific IRQ.
        
        Args:
            irq: IRQ number (0-15)
        """
        cls._operations.append({
            "type": "unmask_irq",
            "irq": irq,
        })
    
    @classmethod
    def trigger_software_interrupt(cls, interrupt_number: int) -> None:
        """
        Trigger a software interrupt.
        
        Args:
            interrupt_number: Interrupt number to trigger
        """
        cls._operations.append({
            "type": "trigger",
            "interrupt": interrupt_number,
        })
    
    @classmethod
    def get_handler(cls, interrupt_number: int) -> Optional[Callable]:
        """Get the handler for an interrupt."""
        return cls._handlers.get(interrupt_number)
    
    @classmethod
    def _reset(cls) -> None:
        """Reset interrupt state (used internally)."""
        cls._handlers = {}
        cls._enabled = False
        cls._operations = []
    
    @classmethod
    def _get_operations(cls) -> list:
        """Get all recorded operations (used by compiler)."""
        return cls._operations.copy()
