"""
pyOS Builder — bootloader (ASM) + C kernel via MinGW-w64
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from .toolchain import Toolchain

if TYPE_CHECKING:
    from .kernel import Kernel


class BuildError(Exception):
    """Raised when build fails, with human-readable reason."""

    def __init__(self, message: str, hint: str = ""):
        self.hint = hint
        full = message
        if hint:
            full = f"{message}\n  Hint: {hint}"
        super().__init__(full)


class OSBuilder:
    """Builds floppy OS images from Python kernel + C runtime."""

    KERNEL_SECTORS = 64  # must match bootloader.asm

    def __init__(self, kernel: "Kernel"):
        self.kernel = kernel
        self.runtime_dir = Path(__file__).parent / "runtime"
        self.bootloader_path = Path(__file__).parent / "boot" / "bootloader.asm"
        self.toolchain = Toolchain()
        self._last_glue: Optional[str] = None
        self._last_symbols: list = []

    def get_asm(self) -> str:
        from .compiler.codegen import CodeGenerator

        gen = CodeGenerator(self.kernel)
        # Prefer C glue content for inspection
        return gen.generate()

    def save_asm(self, output_path: str) -> str:
        glue = self.get_asm()
        Path(output_path).write_text(glue, encoding="utf-8")
        return output_path

    def build_bin(self, output_path: str) -> str:
        self.toolchain.require()
        gcc = self.toolchain.gcc
        nasm = self.toolchain.nasm
        objcopy = self.toolchain.objcopy
        if not objcopy:
            raise BuildError(
                "objcopy not found next to MinGW gcc",
                "Reinstall WinLibs/MinGW so objcopy.exe is on PATH",
            )

        from .compiler.codegen import CodeGenerator

        generator = CodeGenerator(self.kernel)
        glue = generator.generate()
        self._last_glue = glue
        self._last_symbols = generator.get_symbol_map()

        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            glue_c = tmpdir / "glue.c"
            glue_c.write_text(glue, encoding="utf-8")

            # Assemble bootloader
            boot_bin = tmpdir / "bootloader.bin"
            self._run(
                [nasm, "-f", "bin", str(self.bootloader_path), "-o", str(boot_bin)],
                where="NASM bootloader",
                hint="Check pyos/boot/bootloader.asm for syntax errors",
            )

            # Assemble start.S / isr.S with GCC (matches MinGW symbol decoration)
            start_o = tmpdir / "start.o"
            isr_o = tmpdir / "isr.o"
            self._run(
                [gcc, "-m32", "-c", str(self.runtime_dir / "src" / "start.S"), "-o", str(start_o)],
                where="GCC assemble start.S",
            )
            self._run(
                [gcc, "-m32", "-c", str(self.runtime_dir / "src" / "isr.S"), "-o", str(isr_o)],
                where="GCC assemble isr.S",
            )

            c_sources = [
                "debug.c",
                "screen.c",
                "keyboard.c",
                "pic.c",
                "idt.c",
                "heap.c",
                "syscall.c",
                "kmain.c",
            ]
            objects: List[Path] = [start_o, isr_o]
            include = str(self.runtime_dir / "include")
            cflags = [
                "-m32",
                "-ffreestanding",
                "-fno-builtin",
                "-fno-stack-protector",
                "-fno-pic",
                "-fno-asynchronous-unwind-tables",
                "-fno-exceptions",
                "-nostdlib",
                "-Wall",
                "-Wextra",
                "-O1",
                f"-I{include}",
            ]

            for name in c_sources:
                src = self.runtime_dir / "src" / name
                obj = tmpdir / (name.replace(".c", ".o"))
                self._run(
                    [gcc, *cflags, "-c", str(src), "-o", str(obj)],
                    where=f"GCC compile {name}",
                    hint="A C runtime file failed to compile — see compiler output above",
                )
                objects.append(obj)

            glue_o = tmpdir / "glue.o"
            self._run(
                [gcc, *cflags, "-c", str(glue_c), "-o", str(glue_o)],
                where="GCC compile generated glue.c",
                hint="Your Python Screen/Memory ops produced invalid C — check print strings and positions",
            )
            objects.append(glue_o)

            kernel_bin = tmpdir / "kernel.bin"
            map_file = tmpdir / "kernel.map"
            pe = tmpdir / "kernel.pe"
            ld = self.toolchain.ld
            # Link PE/COFF first, then strip to flat binary at VMA 0x1000
            if ld:
                self._run(
                    [
                        ld,
                        "-m",
                        "i386pe",
                        "--image-base",
                        "0",
                        "-T",
                        str(self.runtime_dir / "linker.ld"),
                        "-Map",
                        str(map_file),
                        "-o",
                        str(pe),
                        *[str(o) for o in objects],
                    ],
                    where="ld link kernel (PE)",
                    hint="Missing symbol usually means glue/runtime mismatch",
                )
            else:
                self._run(
                    [
                        gcc,
                        "-m32",
                        "-ffreestanding",
                        "-nostdlib",
                        "-nostartfiles",
                        "-Wl,-T," + str(self.runtime_dir / "linker.ld"),
                        "-Wl,-Map," + str(map_file),
                        "-o",
                        str(pe),
                        *[str(o) for o in objects],
                    ],
                    where="GCC link kernel",
                    hint="Missing symbol usually means glue/runtime mismatch",
                )
            self._run(
                [objcopy, "-O", "binary", str(pe), str(kernel_bin)],
                where="objcopy PE -> flat binary",
            )

            boot_data = boot_bin.read_bytes()
            if len(boot_data) != 512 or boot_data[-2:] != b"\x55\xaa":
                raise BuildError(
                    "Bootloader is invalid (expected 512-byte sector ending with 0x55AA)",
                    "bootloader.asm must end with times 510-($-$$) db 0 / dw 0xAA55",
                )

            kernel_data = kernel_bin.read_bytes()
            max_kernel = self.KERNEL_SECTORS * 512
            if len(kernel_data) > max_kernel:
                raise BuildError(
                    f"Kernel is too large ({len(kernel_data)} bytes > {max_kernel} byte limit)",
                    "Reduce Screen.print strings or raise KERNEL_SECTORS in bootloader + builder",
                )

            # Write symbol map beside output for human debug
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            map_path = out.with_suffix(out.suffix + ".symbols.json")
            map_path.write_text(
                json.dumps(
                    {
                        "symbols": self._last_symbols,
                        "kernel_bytes": len(kernel_data),
                        "heap_size": self.kernel.config.heap_size,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            # Pad to a full 1.44MB floppy so BIOS int 0x13 does not hang in QEMU
            floppy_size = 1474560
            with open(out, "wb") as f:
                f.write(boot_data)
                f.write(kernel_data)
                current = len(boot_data) + len(kernel_data)
                if current < floppy_size:
                    f.write(bytes(floppy_size - current))

            # Also copy map file from linker if present
            link_map = tmpdir / "kernel.map"
            if link_map.exists():
                shutil.copy(link_map, out.with_suffix(out.suffix + ".map"))

        return str(output_path)

    def build_iso(self, output_path: str) -> str:
        """
        Build a bootable image.

        Without grub-mkrescue, writes a floppy-style .bin under the given path
        (QEMU should boot it with -fda). True ISO requires grub-mkrescue.
        """
        out = Path(output_path)
        # Always produce a working floppy image first
        bin_path = out.with_suffix(".bin") if out.suffix.lower() == ".iso" else out
        self.build_bin(str(bin_path))

        if out.suffix.lower() == ".iso":
            # Honest fallback: copy bin to requested path and warn via print
            shutil.copy(bin_path, out)
            print(
                "Warning: created floppy-boot image at "
                f"{out} (not a GRUB ISO). Run with: qemu-system-i386 -fda {out}"
            )
        return str(out)

    def _run(self, cmd: List[str], where: str, hint: str = "") -> None:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return
        err = (result.stderr or result.stdout or "").strip()
        raise BuildError(
            f"Build failed at: {where}\n{err}",
            hint or "Run `pyos check` to verify gcc/nasm/qemu",
        )
