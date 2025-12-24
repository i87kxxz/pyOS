"""
pyOS QEMU Emulator Integration
"""

import subprocess
import shutil
from typing import Optional, List
from pathlib import Path


class QEMUError(Exception):
    """Raised when QEMU fails."""
    pass


class QEMURunner:
    """
    QEMU emulator integration for running pyOS.
    """
    
    def __init__(self, arch: str = "x86"):
        """
        Initialize QEMU runner.
        
        Args:
            arch: Target architecture ("x86" or "x86_64")
        """
        self.arch = arch
        self.qemu_path = self._find_qemu()
    
    def _find_qemu(self) -> str:
        """Find QEMU executable."""
        if self.arch == "x86_64":
            names = ["qemu-system-x86_64", "qemu-system-x86_64.exe"]
        else:
            names = ["qemu-system-i386", "qemu-system-x86_64", 
                     "qemu-system-i386.exe", "qemu-system-x86_64.exe"]
        
        for name in names:
            path = shutil.which(name)
            if path:
                return path
        
        # Return default and hope it works
        return "qemu-system-i386" if self.arch == "x86" else "qemu-system-x86_64"
    
    def run(
        self,
        image_path: str,
        memory: int = 128,
        debug: bool = False,
        extra_args: Optional[List[str]] = None,
    ) -> subprocess.Popen:
        """
        Run OS image in QEMU.
        
        Args:
            image_path: Path to OS image (ISO or BIN)
            memory: Memory in MB (default: 128)
            debug: Enable debug mode
            extra_args: Additional QEMU arguments
        
        Returns:
            QEMU process handle.
        """
        cmd = [self.qemu_path]
        
        # Boot as floppy disk (works best for small OS images)
        cmd.extend(["-fda", image_path])
        
        # Memory
        cmd.extend(["-m", str(memory)])
        
        # Debug mode
        if debug:
            cmd.extend([
                "-s",           # GDB server on port 1234
                "-S",           # Pause at startup
                "-d", "int,cpu_reset",
                "-no-reboot",
                "-no-shutdown",
            ])
        
        # Extra arguments
        if extra_args:
            cmd.extend(extra_args)
        
        # Run QEMU
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return process
        except FileNotFoundError:
            raise QEMUError(
                f"QEMU not found. Please install QEMU:\n"
                f"  Windows: Download from https://www.qemu.org/download/#windows\n"
                f"  Linux: sudo apt install qemu-system-x86\n"
                f"  macOS: brew install qemu"
            )
    
    def run_and_wait(
        self,
        image_path: str,
        memory: int = 128,
        timeout: Optional[int] = None,
    ) -> int:
        """
        Run OS and wait for completion.
        
        Args:
            image_path: Path to OS image
            memory: Memory in MB
            timeout: Timeout in seconds
        
        Returns:
            QEMU exit code.
        """
        process = self.run(image_path, memory)
        
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            return -1
    
    def run_with_serial(
        self,
        image_path: str,
        memory: int = 128,
    ) -> subprocess.Popen:
        """
        Run OS with serial output to console.
        
        Args:
            image_path: Path to OS image
            memory: Memory in MB
        
        Returns:
            QEMU process handle.
        """
        return self.run(
            image_path,
            memory,
            extra_args=["-serial", "stdio", "-display", "none"],
        )
    
    def run_headless(
        self,
        image_path: str,
        memory: int = 128,
    ) -> subprocess.Popen:
        """
        Run OS without display (headless).
        
        Args:
            image_path: Path to OS image
            memory: Memory in MB
        
        Returns:
            QEMU process handle.
        """
        return self.run(
            image_path,
            memory,
            extra_args=["-display", "none", "-serial", "stdio"],
        )
    
    @staticmethod
    def is_available() -> bool:
        """Check if QEMU is available."""
        for name in ["qemu-system-i386", "qemu-system-x86_64"]:
            if shutil.which(name):
                return True
        return False
    
    @staticmethod
    def get_version() -> Optional[str]:
        """Get QEMU version string."""
        for name in ["qemu-system-i386", "qemu-system-x86_64"]:
            path = shutil.which(name)
            if path:
                try:
                    result = subprocess.run(
                        [path, "--version"],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        return result.stdout.split('\n')[0]
                except:
                    pass
        return None
