"""
pyOS Memory Manager - Static and Dynamic Memory Allocation
"""

from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum


class AllocationType(Enum):
    """Memory allocation types"""
    STATIC = "static"
    DYNAMIC = "dynamic"


@dataclass
class MemoryBlock:
    """Represents a memory block"""
    address: int
    size: int
    used: bool = False
    name: Optional[str] = None


@dataclass
class MemoryRegion:
    """Represents a memory region"""
    start: int
    end: int
    name: str
    writable: bool = True
    executable: bool = False


class Memory:
    """
    Memory Manager for pyOS.
    
    Provides both static and dynamic memory allocation.
    
    Example:
        # Static allocation
        buffer = Memory.allocate_static(1024, name="my_buffer")
        
        # Dynamic allocation (heap)
        ptr = Memory.malloc(256)
        Memory.free(ptr)
    """
    
    # Memory layout constants
    KERNEL_START = 0x100000      # 1MB - Kernel starts here
    KERNEL_SIZE = 0x100000       # 1MB for kernel
    HEAP_START = 0x200000        # 2MB - Heap starts here
    HEAP_SIZE = 0x1000000        # 16MB heap
    STACK_TOP = 0x90000          # Stack top (grows down)
    STACK_SIZE = 0x10000         # 64KB stack
    VGA_ADDRESS = 0xB8000        # VGA text buffer
    
    _static_allocations: List[MemoryBlock] = []
    _heap_blocks: List[MemoryBlock] = []
    _next_static_address: int = KERNEL_START + KERNEL_SIZE
    _heap_initialized: bool = False
    _operations: list = []
    
    @classmethod
    def allocate_static(cls, size: int, name: Optional[str] = None, align: int = 4) -> int:
        """
        Allocate static memory (compile-time allocation).
        
        Args:
            size: Size in bytes
            name: Optional name for the allocation
            align: Alignment in bytes (default: 4)
        
        Returns:
            The allocated address.
        
        Example:
            buffer_addr = Memory.allocate_static(1024, name="screen_buffer")
        """
        # Align address
        if cls._next_static_address % align != 0:
            cls._next_static_address += align - (cls._next_static_address % align)
        
        address = cls._next_static_address
        cls._next_static_address += size
        
        block = MemoryBlock(
            address=address,
            size=size,
            used=True,
            name=name,
        )
        cls._static_allocations.append(block)
        
        cls._operations.append({
            "type": "allocate_static",
            "address": address,
            "size": size,
            "name": name,
        })
        
        return address
    
    @classmethod
    def malloc(cls, size: int) -> int:
        """
        Allocate dynamic memory from heap.
        
        Args:
            size: Size in bytes
        
        Returns:
            Pointer to allocated memory, or 0 if failed.
        
        Example:
            ptr = Memory.malloc(256)
            if ptr:
                # Use memory
                Memory.free(ptr)
        """
        cls._operations.append({
            "type": "malloc",
            "size": size,
        })
        
        # Find free block (first-fit algorithm)
        for block in cls._heap_blocks:
            if not block.used and block.size >= size:
                # Split block if much larger
                if block.size > size + 32:
                    new_block = MemoryBlock(
                        address=block.address + size,
                        size=block.size - size,
                        used=False,
                    )
                    cls._heap_blocks.append(new_block)
                    block.size = size
                
                block.used = True
                return block.address
        
        # No free block found, allocate new
        if cls._heap_blocks:
            last = max(cls._heap_blocks, key=lambda b: b.address)
            new_address = last.address + last.size
        else:
            new_address = cls.HEAP_START
        
        if new_address + size > cls.HEAP_START + cls.HEAP_SIZE:
            return 0  # Out of memory
        
        block = MemoryBlock(address=new_address, size=size, used=True)
        cls._heap_blocks.append(block)
        return new_address
    
    @classmethod
    def free(cls, address: int) -> bool:
        """
        Free dynamically allocated memory.
        
        Args:
            address: Pointer returned by malloc
        
        Returns:
            True if freed successfully.
        
        Example:
            Memory.free(ptr)
        """
        cls._operations.append({
            "type": "free",
            "address": address,
        })
        
        for block in cls._heap_blocks:
            if block.address == address:
                block.used = False
                cls._coalesce_free_blocks()
                return True
        return False
    
    @classmethod
    def _coalesce_free_blocks(cls) -> None:
        """Merge adjacent free blocks."""
        cls._heap_blocks.sort(key=lambda b: b.address)
        
        i = 0
        while i < len(cls._heap_blocks) - 1:
            current = cls._heap_blocks[i]
            next_block = cls._heap_blocks[i + 1]
            
            if not current.used and not next_block.used:
                if current.address + current.size == next_block.address:
                    current.size += next_block.size
                    cls._heap_blocks.pop(i + 1)
                    continue
            i += 1
    
    @classmethod
    def realloc(cls, address: int, new_size: int) -> int:
        """
        Reallocate memory with new size.
        
        Args:
            address: Existing pointer
            new_size: New size in bytes
        
        Returns:
            New pointer (may be different from original).
        """
        cls._operations.append({
            "type": "realloc",
            "address": address,
            "new_size": new_size,
        })
        
        # Find existing block
        for block in cls._heap_blocks:
            if block.address == address:
                if block.size >= new_size:
                    return address  # Already big enough
                
                # Allocate new, copy, free old
                new_ptr = cls.malloc(new_size)
                if new_ptr:
                    cls.free(address)
                return new_ptr
        
        return cls.malloc(new_size)
    
    @classmethod
    def calloc(cls, count: int, size: int) -> int:
        """
        Allocate and zero-initialize memory.
        
        Args:
            count: Number of elements
            size: Size of each element
        
        Returns:
            Pointer to zeroed memory.
        
        Example:
            array = Memory.calloc(100, 4)  # 100 integers
        """
        total = count * size
        cls._operations.append({
            "type": "calloc",
            "count": count,
            "size": size,
        })
        return cls.malloc(total)
    
    @classmethod
    def memset(cls, address: int, value: int, size: int) -> None:
        """
        Fill memory with a value.
        
        Args:
            address: Start address
            value: Byte value to fill
            size: Number of bytes
        
        Example:
            Memory.memset(buffer, 0, 1024)  # Zero out buffer
        """
        cls._operations.append({
            "type": "memset",
            "address": address,
            "value": value,
            "size": size,
        })
    
    @classmethod
    def memcpy(cls, dest: int, src: int, size: int) -> None:
        """
        Copy memory from source to destination.
        
        Args:
            dest: Destination address
            src: Source address
            size: Number of bytes to copy
        
        Example:
            Memory.memcpy(dest_buffer, src_buffer, 256)
        """
        cls._operations.append({
            "type": "memcpy",
            "dest": dest,
            "src": src,
            "size": size,
        })
    
    @classmethod
    def read_byte(cls, address: int) -> int:
        """
        Read a byte from memory.
        
        Args:
            address: Memory address
        
        Returns:
            Byte value (0-255).
        """
        cls._operations.append({
            "type": "read_byte",
            "address": address,
        })
        return 0
    
    @classmethod
    def write_byte(cls, address: int, value: int) -> None:
        """
        Write a byte to memory.
        
        Args:
            address: Memory address
            value: Byte value (0-255)
        """
        cls._operations.append({
            "type": "write_byte",
            "address": address,
            "value": value & 0xFF,
        })
    
    @classmethod
    def read_word(cls, address: int) -> int:
        """Read a 16-bit word from memory."""
        cls._operations.append({"type": "read_word", "address": address})
        return 0
    
    @classmethod
    def write_word(cls, address: int, value: int) -> None:
        """Write a 16-bit word to memory."""
        cls._operations.append({
            "type": "write_word",
            "address": address,
            "value": value & 0xFFFF,
        })
    
    @classmethod
    def read_dword(cls, address: int) -> int:
        """Read a 32-bit dword from memory."""
        cls._operations.append({"type": "read_dword", "address": address})
        return 0
    
    @classmethod
    def write_dword(cls, address: int, value: int) -> None:
        """Write a 32-bit dword to memory."""
        cls._operations.append({
            "type": "write_dword",
            "address": address,
            "value": value & 0xFFFFFFFF,
        })
    
    @classmethod
    def get_free_memory(cls) -> int:
        """Get total free heap memory."""
        used = sum(b.size for b in cls._heap_blocks if b.used)
        return cls.HEAP_SIZE - used
    
    @classmethod
    def get_used_memory(cls) -> int:
        """Get total used heap memory."""
        return sum(b.size for b in cls._heap_blocks if b.used)
    
    @classmethod
    def get_memory_map(cls) -> List[MemoryRegion]:
        """
        Get the memory map.
        
        Returns:
            List of memory regions.
        """
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
        """Reset memory state (used internally)."""
        cls._static_allocations = []
        cls._heap_blocks = []
        cls._next_static_address = cls.KERNEL_START + cls.KERNEL_SIZE
        cls._heap_initialized = False
        cls._operations = []
    
    @classmethod
    def _get_operations(cls) -> list:
        """Get all recorded operations (used by compiler)."""
        return cls._operations.copy()
