"""
pyOS GDT (Global Descriptor Table) Management
"""

from typing import List, Optional
from dataclasses import dataclass
from enum import Enum, Flag


class SegmentType(Enum):
    """Segment types for GDT entries"""
    NULL = 0
    CODE_EXECUTE_ONLY = 0x8
    CODE_EXECUTE_READ = 0xA
    CODE_CONFORMING_EXECUTE_ONLY = 0xC
    CODE_CONFORMING_EXECUTE_READ = 0xE
    DATA_READ_ONLY = 0x0
    DATA_READ_WRITE = 0x2
    DATA_EXPAND_DOWN_READ_ONLY = 0x4
    DATA_EXPAND_DOWN_READ_WRITE = 0x6


class PrivilegeLevel(Enum):
    """CPU privilege levels (rings)"""
    RING0 = 0  # Kernel mode
    RING1 = 1
    RING2 = 2
    RING3 = 3  # User mode


@dataclass
class GDTEntry:
    """
    Represents a single GDT entry.
    
    Attributes:
        base: Base address of the segment
        limit: Size of the segment
        segment_type: Type of segment (code/data)
        privilege: Privilege level (ring)
        present: Is segment present in memory
        granularity: Limit granularity (byte or 4KB)
        is_32bit: 32-bit or 16-bit segment
    """
    base: int = 0
    limit: int = 0xFFFFF
    segment_type: SegmentType = SegmentType.DATA_READ_WRITE
    privilege: PrivilegeLevel = PrivilegeLevel.RING0
    present: bool = True
    granularity: bool = True  # True = 4KB, False = 1 byte
    is_32bit: bool = True
    
    def to_bytes(self) -> bytes:
        """Convert GDT entry to 8-byte descriptor."""
        # Limit (bits 0-15)
        limit_low = self.limit & 0xFFFF
        # Base (bits 0-15)
        base_low = self.base & 0xFFFF
        # Base (bits 16-23)
        base_mid = (self.base >> 16) & 0xFF
        
        # Access byte
        access = 0
        if self.present:
            access |= 0x80  # Present bit
        access |= (self.privilege.value << 5)  # DPL
        access |= 0x10  # Descriptor type (1 = code/data)
        access |= self.segment_type.value
        
        # Flags + Limit (bits 16-19)
        flags_limit = (self.limit >> 16) & 0x0F
        if self.granularity:
            flags_limit |= 0x80  # Granularity
        if self.is_32bit:
            flags_limit |= 0x40  # 32-bit
        
        # Base (bits 24-31)
        base_high = (self.base >> 24) & 0xFF
        
        return bytes([
            limit_low & 0xFF,
            (limit_low >> 8) & 0xFF,
            base_low & 0xFF,
            (base_low >> 8) & 0xFF,
            base_mid,
            access,
            flags_limit,
            base_high,
        ])


class GDT:
    """
    Global Descriptor Table Manager.
    
    The GDT defines memory segments for the CPU.
    
    Example:
        gdt = GDT()
        gdt.add_null_descriptor()
        gdt.add_code_segment(base=0, limit=0xFFFFF, ring=0)
        gdt.add_data_segment(base=0, limit=0xFFFFF, ring=0)
        gdt.install()
    """
    
    _entries: List[GDTEntry] = []
    _operations: list = []
    
    def __init__(self):
        """Initialize GDT with empty entries."""
        self._entries = []
        self._operations = []
    
    def add_null_descriptor(self) -> 'GDT':
        """
        Add the required null descriptor (first entry).
        
        Returns:
            Self for chaining.
        
        Example:
            gdt.add_null_descriptor()
        """
        self._entries.append(GDTEntry(
            base=0,
            limit=0,
            segment_type=SegmentType.NULL,
            present=False,
        ))
        self._operations.append({"type": "add_null"})
        return self
    
    def add_code_segment(
        self,
        base: int = 0,
        limit: int = 0xFFFFF,
        ring: int = 0,
        readable: bool = True,
    ) -> 'GDT':
        """
        Add a code segment descriptor.
        
        Args:
            base: Base address (default: 0)
            limit: Segment limit (default: 4GB)
            ring: Privilege level 0-3 (default: 0 = kernel)
            readable: Allow reading code (default: True)
        
        Returns:
            Self for chaining.
        
        Example:
            gdt.add_code_segment(ring=0)  # Kernel code
            gdt.add_code_segment(ring=3)  # User code
        """
        seg_type = SegmentType.CODE_EXECUTE_READ if readable else SegmentType.CODE_EXECUTE_ONLY
        
        self._entries.append(GDTEntry(
            base=base,
            limit=limit,
            segment_type=seg_type,
            privilege=PrivilegeLevel(ring),
        ))
        self._operations.append({
            "type": "add_code",
            "base": base,
            "limit": limit,
            "ring": ring,
        })
        return self
    
    def add_data_segment(
        self,
        base: int = 0,
        limit: int = 0xFFFFF,
        ring: int = 0,
        writable: bool = True,
    ) -> 'GDT':
        """
        Add a data segment descriptor.
        
        Args:
            base: Base address (default: 0)
            limit: Segment limit (default: 4GB)
            ring: Privilege level 0-3 (default: 0 = kernel)
            writable: Allow writing (default: True)
        
        Returns:
            Self for chaining.
        
        Example:
            gdt.add_data_segment(ring=0)  # Kernel data
            gdt.add_data_segment(ring=3)  # User data
        """
        seg_type = SegmentType.DATA_READ_WRITE if writable else SegmentType.DATA_READ_ONLY
        
        self._entries.append(GDTEntry(
            base=base,
            limit=limit,
            segment_type=seg_type,
            privilege=PrivilegeLevel(ring),
        ))
        self._operations.append({
            "type": "add_data",
            "base": base,
            "limit": limit,
            "ring": ring,
        })
        return self
    
    def add_tss_segment(self, base: int, limit: int) -> 'GDT':
        """
        Add a Task State Segment descriptor.
        
        Args:
            base: TSS base address
            limit: TSS size
        
        Returns:
            Self for chaining.
        """
        # TSS descriptor has special format
        self._entries.append(GDTEntry(
            base=base,
            limit=limit,
            segment_type=SegmentType.CODE_EXECUTE_ONLY,  # Will be modified
            privilege=PrivilegeLevel.RING0,
        ))
        self._operations.append({
            "type": "add_tss",
            "base": base,
            "limit": limit,
        })
        return self
    
    def install(self) -> None:
        """
        Install the GDT and reload segment registers.
        
        This must be called after adding all segments.
        
        Example:
            gdt.install()
        """
        self._operations.append({"type": "install"})
    
    def get_selector(self, index: int, ring: int = 0) -> int:
        """
        Get the segment selector for an entry.
        
        Args:
            index: GDT entry index
            ring: Requested privilege level
        
        Returns:
            The segment selector value.
        """
        return (index << 3) | ring
    
    def to_bytes(self) -> bytes:
        """Convert entire GDT to bytes."""
        result = b''
        for entry in self._entries:
            result += entry.to_bytes()
        return result
    
    def get_size(self) -> int:
        """Get GDT size in bytes."""
        return len(self._entries) * 8
    
    def _get_operations(self) -> list:
        """Get all recorded operations (used by compiler)."""
        return self._operations.copy()
    
    @classmethod
    def create_flat_model(cls) -> 'GDT':
        """
        Create a standard flat memory model GDT.
        
        This is the most common setup for modern OS.
        
        Returns:
            Configured GDT instance.
        
        Example:
            gdt = GDT.create_flat_model()
            gdt.install()
        """
        gdt = cls()
        gdt.add_null_descriptor()
        gdt.add_code_segment(ring=0)  # Kernel code
        gdt.add_data_segment(ring=0)  # Kernel data
        gdt.add_code_segment(ring=3)  # User code
        gdt.add_data_segment(ring=3)  # User data
        return gdt
