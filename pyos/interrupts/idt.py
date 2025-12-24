"""
pyOS IDT (Interrupt Descriptor Table)
"""

from typing import List, Optional
from dataclasses import dataclass
from enum import Enum


class GateType(Enum):
    """IDT Gate Types"""
    TASK_GATE = 0x5
    INTERRUPT_GATE_16 = 0x6
    TRAP_GATE_16 = 0x7
    INTERRUPT_GATE_32 = 0xE
    TRAP_GATE_32 = 0xF


@dataclass
class IDTEntry:
    """
    Represents a single IDT entry.
    
    Attributes:
        offset: Handler function address
        selector: Code segment selector
        gate_type: Type of gate
        privilege: Required privilege level to call
        present: Is entry present
    """
    offset: int = 0
    selector: int = 0x08  # Kernel code segment
    gate_type: GateType = GateType.INTERRUPT_GATE_32
    privilege: int = 0
    present: bool = True
    
    def to_bytes(self) -> bytes:
        """Convert IDT entry to 8-byte descriptor."""
        offset_low = self.offset & 0xFFFF
        offset_high = (self.offset >> 16) & 0xFFFF
        
        # Type and attributes byte
        type_attr = self.gate_type.value
        if self.present:
            type_attr |= 0x80
        type_attr |= (self.privilege << 5)
        
        return bytes([
            offset_low & 0xFF,
            (offset_low >> 8) & 0xFF,
            self.selector & 0xFF,
            (self.selector >> 8) & 0xFF,
            0,  # Reserved
            type_attr,
            offset_high & 0xFF,
            (offset_high >> 8) & 0xFF,
        ])


class IDT:
    """
    Interrupt Descriptor Table Manager.
    
    The IDT maps interrupt numbers to handler functions.
    
    Example:
        idt = IDT()
        idt.set_gate(0, divide_error_handler, GateType.TRAP_GATE_32)
        idt.set_gate(33, keyboard_handler, GateType.INTERRUPT_GATE_32)
        idt.install()
    """
    
    MAX_ENTRIES = 256
    
    def __init__(self):
        """Initialize IDT with empty entries."""
        self._entries: List[Optional[IDTEntry]] = [None] * self.MAX_ENTRIES
        self._operations: list = []
    
    def set_gate(
        self,
        index: int,
        handler_address: int,
        gate_type: GateType = GateType.INTERRUPT_GATE_32,
        selector: int = 0x08,
        privilege: int = 0,
    ) -> 'IDT':
        """
        Set an IDT gate entry.
        
        Args:
            index: Interrupt number (0-255)
            handler_address: Address of handler function
            gate_type: Type of gate (default: interrupt gate)
            selector: Code segment selector (default: kernel code)
            privilege: Required privilege level (default: 0)
        
        Returns:
            Self for chaining.
        
        Example:
            idt.set_gate(0, 0x1000, GateType.TRAP_GATE_32)
        """
        if 0 <= index < self.MAX_ENTRIES:
            self._entries[index] = IDTEntry(
                offset=handler_address,
                selector=selector,
                gate_type=gate_type,
                privilege=privilege,
                present=True,
            )
            self._operations.append({
                "type": "set_gate",
                "index": index,
                "handler": handler_address,
                "gate_type": gate_type.name,
            })
        return self
    
    def clear_gate(self, index: int) -> 'IDT':
        """
        Clear an IDT gate entry.
        
        Args:
            index: Interrupt number to clear
        
        Returns:
            Self for chaining.
        """
        if 0 <= index < self.MAX_ENTRIES:
            self._entries[index] = None
            self._operations.append({
                "type": "clear_gate",
                "index": index,
            })
        return self
    
    def install(self) -> None:
        """
        Install the IDT using LIDT instruction.
        
        This must be called after setting up all gates.
        
        Example:
            idt.install()
        """
        self._operations.append({"type": "install"})
    
    def to_bytes(self) -> bytes:
        """Convert entire IDT to bytes."""
        result = b''
        for entry in self._entries:
            if entry:
                result += entry.to_bytes()
            else:
                result += bytes(8)  # Empty entry
        return result
    
    def get_size(self) -> int:
        """Get IDT size in bytes."""
        return self.MAX_ENTRIES * 8
    
    def _get_operations(self) -> list:
        """Get all recorded operations (used by compiler)."""
        return self._operations.copy()
