"""
pyOS Interrupt API — honest: enable/disable/mask emit to C; custom handlers unsupported.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, Optional

from .errors import UnsupportedOpError


class InterruptType(Enum):
    DIVIDE_ERROR = 0
    IRQ_TIMER = 32
    IRQ_KEYBOARD = 33
    SYSCALL = 0x80


@dataclass
class InterruptFrame:
    eip: int = 0
    cs: int = 0
    eflags: int = 0
    esp: int = 0
    ss: int = 0
    error_code: int = 0
    interrupt_number: int = 0


class Interrupts:
    _handlers: Dict[int, Callable] = {}
    _enabled: bool = False
    _operations: list = []

    @classmethod
    def handler(cls, interrupt: InterruptType):
        def decorator(func: Callable) -> Callable:
            raise UnsupportedOpError(
                f"Interrupts.handler({interrupt.name})",
                "Use @kernel.on_keypress / @kernel.on_timer; IDT is owned by the C kernel",
            )

        return decorator

    @classmethod
    def register(cls, interrupt_number: int, handler: Callable) -> None:
        raise UnsupportedOpError("Interrupts.register")

    @classmethod
    def unregister(cls, interrupt_number: int) -> None:
        raise UnsupportedOpError("Interrupts.unregister")

    @classmethod
    def enable(cls) -> None:
        cls._enabled = True
        cls._operations.append({"type": "irq_enable"})

    @classmethod
    def disable(cls) -> None:
        cls._enabled = False
        cls._operations.append({"type": "irq_disable"})

    @classmethod
    def is_enabled(cls) -> bool:
        return cls._enabled

    @classmethod
    def send_eoi(cls, irq: int) -> None:
        cls._operations.append({"type": "irq_eoi", "irq": int(irq)})

    @classmethod
    def mask_irq(cls, irq: int) -> None:
        cls._operations.append({"type": "irq_mask", "irq": int(irq)})

    @classmethod
    def unmask_irq(cls, irq: int) -> None:
        cls._operations.append({"type": "irq_unmask", "irq": int(irq)})

    @classmethod
    def trigger_software_interrupt(cls, interrupt_number: int) -> None:
        raise UnsupportedOpError("Interrupts.trigger_software_interrupt")

    @classmethod
    def get_handler(cls, interrupt_number: int) -> Optional[Callable]:
        return None

    @classmethod
    def _reset(cls) -> None:
        cls._handlers = {}
        cls._enabled = False
        cls._operations = []

    @classmethod
    def _get_operations(cls) -> list:
        return cls._operations.copy()
