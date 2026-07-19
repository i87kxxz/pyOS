"""
pyOS Builder — Multiboot ELF kernel (QEMU -kernel) via MinGW-w64
"""

from __future__ import annotations

import json
import shutil
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


# Soft cap so runaway glue cannot fill the disk; far above the old 64-sector floppy limit.
MAX_KERNEL_BYTES = 8 * 1024 * 1024


class OSBuilder:
    """Builds Multiboot ELF kernels from Python DSL + C kernel sources."""

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
            ("switch.o", k / "arch" / "x86" / "switch.S"),
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
            ("ext2.o", k / "fs" / "ext2.c"),
            ("pci.o", k / "drivers" / "pci.c"),
            ("virtio_blk.o", k / "drivers" / "virtio_blk.c"),
            ("virtio_net.o", k / "drivers" / "virtio_net.c"),
            ("blkdev.o", k / "drivers" / "blkdev.c"),
            ("net.o", k / "net" / "net.c"),
            ("socket.o", k / "net" / "socket.c"),
            ("shell.o", k / "drivers" / "shell.c"),
            ("kmain.o", k / "kmain.c"),
        ]

    def build_bin(self, output_path: str) -> str:
        self.toolchain.require()
        gcc = self.toolchain.gcc
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

            include = str(self.kernel_dir / "include")
            cflags = [
                "-m32",
                "-ffreestanding",
                "-fno-builtin",
                "-fno-stack-protector",
                "-fno-pic",
                "-fno-asynchronous-unwind-tables",
                "-fno-exceptions",
                # Freestanding i386: never emit SSE (QEMU boots without OSFXSR → #UD).
                "-mno-sse",
                "-mno-sse2",
                "-mno-mmx",
                "-mfpmath=387",
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

            map_file = tmpdir / "kernel.map"
            pe = tmpdir / "kernel.pe"
            elf = tmpdir / "kernel.elf"
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

            # MinGW links PE; QEMU Multiboot -kernel expects ELF32.
            self._run(
                [objcopy, "-O", "elf32-i386", str(pe), str(elf)],
                where="objcopy PE -> Multiboot ELF32",
            )

            kernel_data = elf.read_bytes()
            if len(kernel_data) < 4 or kernel_data[:4] != b"\x7fELF":
                raise BuildError("objcopy did not produce a valid ELF kernel image")
            if b"\x02\xb0\xad\x1b" not in kernel_data[:8192]:
                raise BuildError(
                    "Multiboot header magic missing in first 8KiB",
                    "Check .multiboot section in start.S / linker.ld",
                )
            if len(kernel_data) > MAX_KERNEL_BYTES:
                raise BuildError(
                    f"Kernel too large ({len(kernel_data)} > {MAX_KERNEL_BYTES})",
                    "Reduce glue/heap seeds or raise MAX_KERNEL_BYTES in builder.py",
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
                        "boot": "multiboot-elf",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            out.write_bytes(kernel_data)

            if map_file.exists():
                shutil.copy(map_file, out.with_suffix(out.suffix + ".map"))

        return str(output_path)

    def build_iso(self, output_path: str) -> str:
        """ISO format currently emits the same Multiboot ELF (boot with qemu -kernel)."""
        out = Path(output_path)
        bin_path = out.with_suffix(".bin") if out.suffix.lower() == ".iso" else out
        self.build_bin(str(bin_path))
        if out.suffix.lower() == ".iso":
            shutil.copy(bin_path, out)
            print(
                f"Warning: Multiboot ELF written to {out} (not a GRUB ISO). "
                f"Run: qemu-system-i386 -kernel {out}"
            )
        return str(out)

    def _run(self, cmd: List[str], where: str, hint: str = "") -> None:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return
        err = (result.stderr or result.stdout or "").strip()
        raise BuildError(f"Build failed at: {where}\n{err}", hint or "Run `pyos check`")
