"""Build freestanding i386 ash ELF for pyOS userland."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
ASH_C = ROOT / "pyos" / "user" / "ash.c"
USER_LD = ROOT / "pyos" / "user" / "user.ld"
DEFAULT_OUT = ROOT / "third_party" / "ash-i386"


def _which(name: str) -> Optional[str]:
    return shutil.which(name)


def build_ash_elf(output: Optional[Path] = None) -> Path:
    """Compile ash.c to a Linux-ish ELF32 ET_EXEC at 0x08048000."""
    out = Path(output) if output else DEFAULT_OUT
    gcc = _which("gcc")
    ld = _which("ld")
    objcopy = _which("objcopy")
    if not gcc or not objcopy:
        raise RuntimeError("gcc/objcopy required to build ash ELF")

    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        obj = t / "ash.o"
        pe = t / "ash.pe"
        elf = t / "ash.elf"
        subprocess.check_call(
            [
                gcc,
                "-m32",
                "-ffreestanding",
                "-fno-builtin",
                "-fno-stack-protector",
                "-fno-pic",
                "-nostdlib",
                "-O1",
                "-c",
                str(ASH_C),
                "-o",
                str(obj),
            ]
        )
        if ld:
            subprocess.check_call(
                [
                    ld,
                    "-m",
                    "i386pe",
                    "-T",
                    str(USER_LD),
                    "-o",
                    str(pe),
                    str(obj),
                ]
            )
        else:
            subprocess.check_call(
                [
                    gcc,
                    "-m32",
                    "-ffreestanding",
                    "-nostdlib",
                    "-Wl,-T," + str(USER_LD),
                    "-o",
                    str(pe),
                    str(obj),
                ]
            )
        subprocess.check_call([objcopy, "-O", "elf32-i386", str(pe), str(elf)])
        data = elf.read_bytes()
        if data[:4] != b"\x7fELF":
            raise RuntimeError("ash ELF build failed (bad magic)")
        out.write_bytes(data)
    return out


if __name__ == "__main__":
    path = build_ash_elf()
    print(f"wrote {path} ({path.stat().st_size} bytes)")
