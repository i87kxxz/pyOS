"""
pyOS QEMU Emulator Integration
"""

from __future__ import annotations

import subprocess
import shutil
from typing import Optional, List
from pathlib import Path

from .build.toolchain import Toolchain


class QEMUError(Exception):
    """Raised when QEMU fails."""
    pass


class QEMURunner:
    """QEMU emulator integration for running pyOS."""

    def __init__(self, arch: str = "x86"):
        self.arch = arch
        tools = Toolchain()
        self.qemu_path = tools.qemu or self._find_qemu()

    def _find_qemu(self) -> str:
        if self.arch == "x86_64":
            names = ["qemu-system-x86_64", "qemu-system-x86_64.exe"]
        else:
            names = [
                "qemu-system-i386",
                "qemu-system-x86_64",
                "qemu-system-i386.exe",
                "qemu-system-x86_64.exe",
            ]
        for name in names:
            path = shutil.which(name)
            if path:
                return path
        for directory in [r"C:\Program Files\qemu", r"C:\Program Files (x86)\qemu"]:
            for name in names:
                candidate = Path(directory) / name
                if candidate.exists():
                    return str(candidate)
        return "qemu-system-i386" if self.arch == "x86" else "qemu-system-x86_64"

    def _boot_args(self, image_path: str) -> List[str]:
        # pyOS images are raw floppy disks (bootloader + kernel)
        return ["-drive", f"format=raw,file={image_path},if=floppy"]

    def run(
        self,
        image_path: str,
        memory: int = 128,
        debug: bool = False,
        extra_args: Optional[List[str]] = None,
        serial_stdio: bool = False,
    ) -> subprocess.Popen:
        if not Path(image_path).exists():
            raise QEMUError(
                f"Image not found: {image_path}\n"
                "  Hint: build first with kernel.build('myos.bin') or pyos build main.py -o myos.bin"
            )

        cmd = [self.qemu_path]
        cmd.extend(self._boot_args(image_path))
        cmd.extend(["-boot", "order=a"])
        cmd.extend(["-m", str(memory)])

        if serial_stdio or debug:
            cmd.extend(["-serial", "stdio", "-debugcon", "stdio"])

        if debug:
            cmd.extend([
                "-s",
                "-S",
                "-d", "guest_errors",
                "-no-reboot",
                "-no-shutdown",
            ])

        if extra_args:
            cmd.extend(extra_args)

        try:
            return subprocess.Popen(cmd)
        except FileNotFoundError:
            raise QEMUError(
                "QEMU not found.\n"
                "  Install: winget install -e --id SoftwareFreedomConservancy.QEMU"
            )

    def run_and_wait(
        self,
        image_path: str,
        memory: int = 128,
        timeout: Optional[int] = None,
    ) -> int:
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
        return self.run(image_path, memory, serial_stdio=True, extra_args=["-display", "none"])

    def run_headless(
        self,
        image_path: str,
        memory: int = 128,
    ) -> subprocess.Popen:
        return self.run(
            image_path,
            memory,
            serial_stdio=True,
            extra_args=["-display", "none"],
        )

    @staticmethod
    def is_available() -> bool:
        return Toolchain().qemu is not None

    @staticmethod
    def get_version() -> Optional[str]:
        tools = Toolchain()
        if not tools.qemu:
            return None
        try:
            result = subprocess.run(
                [tools.qemu, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.split("\n")[0]
        except Exception:
            pass
        return None
