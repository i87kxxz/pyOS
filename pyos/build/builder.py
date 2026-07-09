"""
pyOS Builder — bootloader (ASM) + C kernel via MinGW-w64
"""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple

from .toolchain import Toolchain

if TYPE_CHECKING:
    from ..api.kernel import Kernel


class BuildError(Exception):
    def __init__(self, message: str, hint: str = ""):
        self.hint = hint
        full = message
        if hint:
            full = f"{message}\n  Hint: {hint}"
        super().__init__(full)


class OSBuilder:
    """Builds floppy OS images from Python kernel + C kernel sources."""

    KERNEL_SECTORS = 64  # must match bootloader.asm

    def __init__(self, kernel: "Kernel"):
        self.kernel = kernel
        self.kernel_dir = Path(__file__).resolve().parent.parent / "kernel"
        self.bootloader_path = Path(__file__).resolve().parent.parent / "boot" / "bootloader.asm"
        self.toolchain = Toolchain()
        self._last_glue: Optional[str] = None
        self._last_symbols: list = []

    def get_asm(self) -> str:
        from .codegen import CodeGenerator

        return CodeGenerator(self.kernel).generate()

    def save_asm(self, output_path: str) -> str:
        glue = self.get_asm()
        Path(output_path).write_text(glue, encoding="utf-8")
        return output_path

    def _source_list(self) -> List[Tuple[str, Path]]:
        """Return (obj_name, source_path) pairs."""
        k = self.kernel_dir
        return [
            ("start.o", k / "arch" / "x86" / "start.S"),
            ("isr.o", k / "arch" / "x86" / "isr.S"),
            ("debug.o", k / "lib" / "debug.c"),
            ("string.o", k / "lib" / "string.c"),
            ("screen.o", k / "drivers" / "screen.c"),
            ("keyboard.o", k / "drivers" / "keyboard.c"),
            ("pit.o", k / "drivers" / "pit.c"),
            ("floppy.o", k / "drivers" / "floppy.c"),
            ("pic.o", k / "arch" / "x86" / "pic.c"),
            ("idt.o", k / "arch" / "x86" / "idt.c"),
            ("gdt.o", k / "arch" / "x86" / "gdt.c"),
            ("paging.o", k / "arch" / "x86" / "paging.c"),
            ("syscall.o", k / "arch" / "x86" / "syscall.c"),
            ("usercopy.o", k / "arch" / "x86" / "usercopy.c"),
            ("heap.o", k / "mm" / "heap.c"),
            ("pmm.o", k / "mm" / "pmm.c"),
            ("task.o", k / "proc" / "task.c"),
            ("elf.o", k / "proc" / "elf.c"),
            ("vfs.o", k / "fs" / "vfs.c"),
            ("ramfs.o", k / "fs" / "ramfs.c"),
            ("fat12.o", k / "fs" / "fat12.c"),
            ("shell.o", k / "drivers" / "shell.c"),
            ("kmain.o", k / "kmain.c"),
        ]

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

        from .codegen import CodeGenerator

        generator = CodeGenerator(self.kernel)
        glue = generator.generate()
        self._last_glue = glue
        self._last_symbols = generator.get_symbol_map()

        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            glue_c = tmpdir / "glue.c"
            glue_c.write_text(glue, encoding="utf-8")

            boot_bin = tmpdir / "bootloader.bin"
            self._run(
                [nasm, "-f", "bin", str(self.bootloader_path), "-o", str(boot_bin)],
                where="NASM bootloader",
                hint="Check pyos/boot/bootloader.asm",
            )

            include = str(self.kernel_dir / "include")
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
                "-Wno-unused-parameter",
                "-O1",
                f"-I{include}",
            ]

            objects: List[Path] = []
            for obj_name, src in self._source_list():
                if not src.exists():
                    raise BuildError(f"Missing kernel source: {src}")
                obj = tmpdir / obj_name
                if src.suffix.lower() in (".s", ".S"):
                    self._run(
                        [gcc, "-m32", "-c", str(src), "-o", str(obj)],
                        where=f"GCC assemble {src.name}",
                    )
                else:
                    self._run(
                        [gcc, *cflags, "-c", str(src), "-o", str(obj)],
                        where=f"GCC compile {src.name}",
                    )
                objects.append(obj)

            glue_o = tmpdir / "glue.o"
            self._run(
                [gcc, *cflags, "-c", str(glue_c), "-o", str(glue_o)],
                where="GCC compile generated glue.c",
            )
            objects.append(glue_o)

            kernel_bin = tmpdir / "kernel.bin"
            map_file = tmpdir / "kernel.map"
            pe = tmpdir / "kernel.pe"
            ld = self.toolchain.ld
            if ld:
                self._run(
                    [
                        ld,
                        "-m",
                        "i386pe",
                        "--image-base",
                        "0",
                        "-T",
                        str(self.kernel_dir / "linker.ld"),
                        "-Map",
                        str(map_file),
                        "-o",
                        str(pe),
                        *[str(o) for o in objects],
                    ],
                    where="ld link kernel (PE)",
                )
            else:
                self._run(
                    [
                        gcc,
                        "-m32",
                        "-ffreestanding",
                        "-nostdlib",
                        "-nostartfiles",
                        "-Wl,-T," + str(self.kernel_dir / "linker.ld"),
                        "-Wl,-Map," + str(map_file),
                        "-o",
                        str(pe),
                        *[str(o) for o in objects],
                    ],
                    where="GCC link kernel",
                )
            self._run(
                [objcopy, "-O", "binary", str(pe), str(kernel_bin)],
                where="objcopy PE -> flat binary",
            )

            boot_data = boot_bin.read_bytes()
            if len(boot_data) != 512 or boot_data[-2:] != b"\x55\xaa":
                raise BuildError("Bootloader invalid (need 512 bytes ending 0x55AA)")

            kernel_data = kernel_bin.read_bytes()
            max_kernel = self.KERNEL_SECTORS * 512
            if len(kernel_data) > max_kernel:
                raise BuildError(
                    f"Kernel too large ({len(kernel_data)} > {max_kernel})",
                    "Raise KERNEL_SECTORS in bootloader.asm and OSBuilder",
                )

            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            map_path = out.with_suffix(out.suffix + ".symbols.json")
            map_path.write_text(
                json.dumps(
                    {
                        "symbols": self._last_symbols,
                        "kernel_bytes": len(kernel_data),
                        "heap_size": self.kernel.config.heap_size,
                        "capabilities": self.kernel.capabilities,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            floppy_size = 1474560
            image = bytearray(floppy_size)
            image[0:512] = boot_data
            image[512 : 512 + len(kernel_data)] = kernel_data

            # Optional FAT12 seed region after kernel (Phase 5)
            if self.kernel.config.enable_filesystem and self.kernel._seed_files:
                fat_blob = self._build_fat12_seeds(self.kernel._seed_files)
                fat_off = 512 + self.KERNEL_SECTORS * 512
                if fat_off + len(fat_blob) > floppy_size:
                    raise BuildError("FAT seed data exceeds floppy size")
                image[fat_off : fat_off + len(fat_blob)] = fat_blob

            out.write_bytes(bytes(image))

            if map_file.exists():
                shutil.copy(map_file, out.with_suffix(out.suffix + ".map"))

        return str(output_path)

    def _build_fat12_seeds(self, seeds: dict) -> bytes:
        """Minimal embedded file table: count + (name[11] + size u32 + data)*n"""
        parts = [struct.pack("<I", len(seeds))]
        for name, data in seeds.items():
            n = name.upper().replace("/", "_")[:11].ljust(11)
            parts.append(n.encode("ascii", errors="replace"))
            parts.append(struct.pack("<I", len(data)))
            parts.append(data)
        return b"".join(parts)

    def build_iso(self, output_path: str) -> str:
        out = Path(output_path)
        bin_path = out.with_suffix(".bin") if out.suffix.lower() == ".iso" else out
        self.build_bin(str(bin_path))
        if out.suffix.lower() == ".iso":
            shutil.copy(bin_path, out)
            print(
                f"Warning: floppy-boot image at {out} (not GRUB ISO). "
                f"Run: qemu-system-i386 -fda {out}"
            )
        return str(out)

    def _run(self, cmd: List[str], where: str, hint: str = "") -> None:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return
        err = (result.stderr or result.stdout or "").strip()
        raise BuildError(f"Build failed at: {where}\n{err}", hint or "Run `pyos check`")
