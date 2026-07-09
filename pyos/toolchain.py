"""
pyOS toolchain discovery (MinGW-w64 GCC, NASM, QEMU)
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple


INSTALL_HINTS = {
    "gcc": (
        "MinGW-w64 GCC not found.\n"
        "  Install: winget install -e --id BrechtSanders.WinLibs.POSIX.UCRT\n"
        "  Then restart the terminal so gcc is on PATH."
    ),
    "nasm": (
        "NASM not found.\n"
        "  Install: winget install -e --id NASM.NASM\n"
        "  Or download: https://www.nasm.us/"
    ),
    "qemu": (
        "QEMU not found.\n"
        "  Install: winget install -e --id SoftwareFreedomConservancy.QEMU\n"
        "  Or download: https://www.qemu.org/download/"
    ),
}


def _which_many(names: List[str], extra_dirs: Optional[List[str]] = None) -> Optional[str]:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    if extra_dirs:
        for directory in extra_dirs:
            if not directory or not os.path.isdir(directory):
                continue
            for name in names:
                candidate = os.path.join(directory, name)
                if os.path.isfile(candidate):
                    return candidate
                if os.name == "nt" and not name.endswith(".exe"):
                    candidate = os.path.join(directory, name + ".exe")
                    if os.path.isfile(candidate):
                        return candidate
    return None


def _mingw_dirs() -> List[str]:
    dirs: List[str] = []
    local = os.environ.get("LOCALAPPDATA", "")
    winget = os.path.join(local, "Microsoft", "WinGet", "Packages")
    if os.path.isdir(winget):
        try:
            for entry in os.listdir(winget):
                if "WinLibs" in entry or "mingw" in entry.lower():
                    base = os.path.join(winget, entry)
                    for root, _, files in os.walk(base):
                        if "gcc.exe" in files or "gcc" in files:
                            dirs.append(root)
                            break
        except OSError:
            pass
    for p in [
        r"C:\mingw64\bin",
        r"C:\msys64\mingw64\bin",
        r"C:\Program Files\mingw-w64\mingw64\bin",
    ]:
        dirs.append(p)
    return dirs


def _nasm_dirs() -> List[str]:
    local = os.environ.get("LOCALAPPDATA", "")
    return [
        os.path.join(local, "bin", "NASM"),
        r"C:\Program Files\NASM",
        r"C:\NASM",
    ]


def _qemu_dirs() -> List[str]:
    return [
        r"C:\Program Files\qemu",
        r"C:\Program Files (x86)\qemu",
    ]


@dataclass
class ToolStatus:
    name: str
    path: Optional[str]
    version: Optional[str]
    ok: bool
    detail: str = ""


class Toolchain:
    """Locate and validate build tools."""

    def __init__(self) -> None:
        self.gcc = _which_many(["gcc", "x86_64-w64-mingw32-gcc"], _mingw_dirs())
        self.objcopy = _which_many(["objcopy"], _mingw_dirs())
        self.ld = _which_many(["ld"], _mingw_dirs())
        self.nasm = _which_many(["nasm"], _nasm_dirs())
        self.qemu = _which_many(
            ["qemu-system-i386", "qemu-system-x86_64"],
            _qemu_dirs(),
        )

    def gcc_supports_m32(self) -> Tuple[bool, str]:
        if not self.gcc:
            return False, INSTALL_HINTS["gcc"]
        probe = (
            "int main(void){return 0;}\n"
        )
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "probe.c"
            obj = Path(tmp) / "probe.o"
            src.write_text(probe, encoding="ascii")
            result = subprocess.run(
                [self.gcc, "-m32", "-c", str(src), "-o", str(obj)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return False, (
                    "GCC found but cannot compile with -m32.\n"
                    f"  gcc: {self.gcc}\n"
                    f"  error: {result.stderr.strip() or result.stdout.strip()}"
                )
            return True, "ok"

    def status(self) -> List[ToolStatus]:
        items: List[ToolStatus] = []

        gcc_ver = None
        gcc_ok = False
        gcc_detail = INSTALL_HINTS["gcc"]
        if self.gcc:
            r = subprocess.run([self.gcc, "--version"], capture_output=True, text=True)
            gcc_ver = (r.stdout.splitlines() or [""])[0]
            m32_ok, m32_detail = self.gcc_supports_m32()
            gcc_ok = m32_ok
            gcc_detail = m32_detail if not m32_ok else f"path={self.gcc}"
        items.append(ToolStatus("gcc (-m32)", self.gcc, gcc_ver, gcc_ok, gcc_detail))

        nasm_ver = None
        nasm_ok = bool(self.nasm)
        if self.nasm:
            r = subprocess.run([self.nasm, "-v"], capture_output=True, text=True)
            nasm_ver = (r.stdout or r.stderr).strip().splitlines()[0] if (r.stdout or r.stderr) else None
        items.append(
            ToolStatus(
                "nasm",
                self.nasm,
                nasm_ver,
                nasm_ok,
                "" if nasm_ok else INSTALL_HINTS["nasm"],
            )
        )

        qemu_ver = None
        qemu_ok = bool(self.qemu)
        if self.qemu:
            r = subprocess.run([self.qemu, "--version"], capture_output=True, text=True)
            qemu_ver = (r.stdout.splitlines() or [""])[0]
        items.append(
            ToolStatus(
                "qemu",
                self.qemu,
                qemu_ver,
                qemu_ok,
                "" if qemu_ok else INSTALL_HINTS["qemu"],
            )
        )
        return items

    def require(self) -> None:
        problems = [s for s in self.status() if not s.ok]
        if not problems:
            return
        lines = ["pyOS build tools are incomplete:", ""]
        for p in problems:
            lines.append(f"- {p.name}: missing or broken")
            if p.detail:
                lines.append(f"  {p.detail}")
            lines.append("")
        raise RuntimeError("\n".join(lines))
