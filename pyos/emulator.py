"""
pyOS QEMU Emulator Integration
"""

from __future__ import annotations

import subprocess
import shutil
from typing import Optional, List
from pathlib import Path

from .build.toolchain import Toolchain
from .build.rootfs import virtio_disk_args, virtio_net_args


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
        """Multiboot ELF → -kernel; legacy raw floppy → -drive if=floppy."""
        path = Path(image_path)
        try:
            magic = path.read_bytes()[:4]
        except OSError:
            magic = b""
        if magic == b"\x7fELF":
            return ["-kernel", str(path)]
        return ["-drive", f"format=raw,file={image_path},if=floppy"]

    @staticmethod
    def disk_args(disk_path: Optional[str]) -> List[str]:
        if not disk_path:
            return []
        return virtio_disk_args(disk_path)

    @staticmethod
    def net_args(enabled: bool = True, hostfwd: Optional[str] = None) -> List[str]:
        if not enabled:
            return []
        return virtio_net_args(hostfwd=hostfwd)

    def run(
        self,
        image_path: str,
        memory: int = 128,
        debug: bool = False,
        extra_args: Optional[List[str]] = None,
        serial_stdio: bool = False,
        disk: Optional[str] = None,
        network: bool = False,
        hostfwd: Optional[str] = None,
    ) -> subprocess.Popen:
        if not Path(image_path).exists():
            raise QEMUError(
                f"Image not found: {image_path}\n"
                "  Hint: build first with kernel.build('myos.bin') or pyos build main.py -o myos.bin"
            )

        cmd = [self.qemu_path]
        boot_args = self._boot_args(image_path)
        cmd.extend(boot_args)
        if boot_args[:1] != ["-kernel"]:
            cmd.extend(["-boot", "order=a"])
        cmd.extend(["-m", str(memory)])
        cmd.extend(self.disk_args(disk))
        cmd.extend(self.net_args(network, hostfwd=hostfwd))

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
        disk: Optional[str] = None,
        network: bool = False,
    ) -> int:
        process = self.run(image_path, memory, disk=disk, network=network)
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            return -1

    def run_with_serial(
        self,
        image_path: str,
        memory: int = 128,
        disk: Optional[str] = None,
        network: bool = False,
    ) -> subprocess.Popen:
        return self.run(
            image_path,
            memory,
            serial_stdio=True,
            disk=disk,
            network=network,
            extra_args=["-display", "none"],
        )

    def run_headless(
        self,
        image_path: str,
        memory: int = 128,
        disk: Optional[str] = None,
        network: bool = False,
    ) -> subprocess.Popen:
        return self.run(
            image_path,
            memory,
            serial_stdio=True,
            disk=disk,
            network=network,
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
