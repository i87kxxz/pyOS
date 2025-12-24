"""
pyOS Assembler - Assembly to Machine Code
"""

import subprocess
import tempfile
import os
from typing import Optional
from pathlib import Path


class AssemblerError(Exception):
    """Raised when assembly fails."""
    pass


class Assembler:
    """
    Assembles x86/x86_64 Assembly code to machine code.
    
    Uses NASM (Netwide Assembler) for assembly.
    """
    
    def __init__(self, arch: str = "x86"):
        """
        Initialize assembler.
        
        Args:
            arch: Target architecture ("x86" or "x86_64")
        """
        self.arch = arch
        self.nasm_path = self._find_nasm()
    
    def _find_nasm(self) -> str:
        """Find NASM executable."""
        # Try common locations
        paths = [
            "nasm",
            "/usr/bin/nasm",
            "/usr/local/bin/nasm",
            "C:\\Program Files\\NASM\\nasm.exe",
            "C:\\NASM\\nasm.exe",
        ]
        
        for path in paths:
            try:
                result = subprocess.run(
                    [path, "-v"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    return path
            except FileNotFoundError:
                continue
        
        return "nasm"  # Hope it's in PATH
    
    def assemble(self, asm_code: str, output_format: str = "bin") -> bytes:
        """
        Assemble code to machine code.
        
        Args:
            asm_code: Assembly source code
            output_format: Output format (bin, elf, elf64)
        
        Returns:
            Binary machine code.
        
        Raises:
            AssemblerError: If assembly fails.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            asm_file = Path(tmpdir) / "kernel.asm"
            out_file = Path(tmpdir) / "kernel.bin"
            
            # Write assembly to file
            asm_file.write_text(asm_code)
            
            # Determine format
            if self.arch == "x86_64":
                fmt = "elf64" if output_format == "elf" else output_format
            else:
                fmt = "elf32" if output_format == "elf" else output_format
            
            # Run NASM
            cmd = [
                self.nasm_path,
                "-f", fmt,
                "-o", str(out_file),
                str(asm_file),
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )
            
            if result.returncode != 0:
                raise AssemblerError(f"NASM failed:\n{result.stderr}")
            
            # Read binary output
            return out_file.read_bytes()
    
    def assemble_to_file(self, asm_code: str, output_path: str, output_format: str = "bin") -> str:
        """
        Assemble code and write to file.
        
        Args:
            asm_code: Assembly source code
            output_path: Output file path
            output_format: Output format
        
        Returns:
            Path to output file.
        """
        binary = self.assemble(asm_code, output_format)
        
        with open(output_path, "wb") as f:
            f.write(binary)
        
        return output_path
    
    def link(self, object_files: list, output_path: str) -> str:
        """
        Link object files into executable.
        
        Args:
            object_files: List of object file paths
            output_path: Output executable path
        
        Returns:
            Path to linked executable.
        """
        # Use ld for linking
        cmd = ["ld", "-m"]
        
        if self.arch == "x86_64":
            cmd.append("elf_x86_64")
        else:
            cmd.append("elf_i386")
        
        cmd.extend(["-T", "linker.ld"])
        cmd.extend(["-o", output_path])
        cmd.extend(object_files)
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise AssemblerError(f"Linker failed:\n{result.stderr}")
        
        return output_path
    
    @staticmethod
    def is_nasm_available() -> bool:
        """Check if NASM is available."""
        try:
            result = subprocess.run(
                ["nasm", "-v"],
                capture_output=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    @staticmethod
    def get_nasm_version() -> Optional[str]:
        """Get NASM version string."""
        try:
            result = subprocess.run(
                ["nasm", "-v"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except FileNotFoundError:
            pass
        return None
