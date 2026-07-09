# pyOS

**Build a real x86 operating system — in Python.**

You write a small, readable Python API.  
pyOS turns it into a freestanding **C kernel** + **ASM bootloader**, then boots it in **QEMU**.

```text
  Python DSL  ──►  C glue + C kernel  ──►  GCC -m32  ─┐
                                                      ├─►  os.bin  ─►  QEMU
  bootloader.asm  ──────────────────────►  NASM      ─┘
```

[![PyPI](https://img.shields.io/pypi/v/pyOS-kernel.svg)](https://pypi.org/project/pyOS-kernel/)
[![Python](https://img.shields.io/pypi/pyversions/pyOS-kernel.svg)](https://pypi.org/project/pyOS-kernel/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Table of contents

1. [What is pyOS?](#what-is-pyos)
2. [What it is not](#what-it-is-not)
3. [Features](#features)
4. [Requirements](#requirements)
5. [Install](#install)
6. [Quick start](#quick-start)
7. [CLI](#cli)
8. [API overview](#api-overview)
9. [Capabilities (flags)](#capabilities-flags)
10. [Project layout](#project-layout)
11. [Examples](#examples)
12. [Guest shell](#guest-shell)
13. [Debugging](#debugging)
14. [Tests](#tests)
15. [Architecture](#architecture)
16. [Roadmap](#roadmap)
17. [Security notes](#security-notes)
18. [Contributing](#contributing)
19. [License](#license)

---

## What is pyOS?

pyOS is a **Python DSL for building real OS kernels**.

| Layer | Role |
|-------|------|
| **Python** | Describe boot screens, handlers, and features at *build time* |
| **Codegen** | Emit honest C glue (no silent stubs) |
| **C kernel** | VGA, keyboard, heap, timer, IDT/PIC, syscalls, paging, tasks, VFS, shell |
| **ASM** | 16→32-bit bootloader only |

Typical flow:

```bash
pip install pyOS-kernel
# write main.py with Kernel + Screen
pyos build main.py -o myos.bin
pyos run myos.bin
pyos debug myos.bin
```

---

## What it is not

- **Not** CPython running inside the kernel  
- **Not** a full Linux clone (no networking stack, no ext4, no SMP yet)  
- **Not** “fake” APIs: unsupported calls raise `CapabilityError` / `UnsupportedOpError`

Boot functions run on your **host** during `build()`. Only recorded operations become C calls in the guest.

---

## Features

**Core**

- Freestanding **32-bit x86** kernel + floppy boot image
- VGA text mode (`Screen.clear`, `print`, colors, cursor, scroll)
- PS/2 keyboard IRQ + optional echo / shell input
- PIT timer + `@kernel.on_timer`
- Human-readable **serial panics** (`pyos debug`)

**Memory & syscalls**

- Free-list **heap** (`malloc` / `free` / `calloc` / `realloc`)
- Syscalls: `EXIT`, `READ`, `WRITE`, `OPEN`, `CLOSE`, `GETPID`, `MALLOC`, `FREE`, `SLEEP`, `TIME`, `YIELD`, `SPAWN`

**Security-oriented building blocks**

- Optional **GDT + TSS**
- Optional **paging** (identity map)
- `copy_from_user` / range checks when `enable_user_mode=True`

**OS services**

- Cooperative **process table** + round-robin on IRQ0
- **VFS / ramfs** + build-time `seed_file(...)`
- Built-in **shell**: `help`, `ls`, `cat`, `ps`, `free`, `clear`, `echo`

---

## Requirements

| Tool | Why | Install (Windows) |
|------|-----|-------------------|
| **Python 3.8+** | DSL + CLI | [python.org](https://www.python.org/) |
| **MinGW-w64 GCC** (`-m32`) | Compile the C kernel | `winget install -e --id BrechtSanders.WinLibs.POSIX.UCRT` |
| **NASM** | Assemble the bootloader | `winget install -e --id NASM.NASM` |
| **QEMU** | Run the OS | `winget install -e --id SoftwareFreedomConservancy.QEMU` |

Verify:

```bash
pyos check
```

---

## Install

**From PyPI**

```bash
pip install pyOS-kernel
```

**From source (dev)**

```bash
git clone https://github.com/i87kxxz/pyOS.git
cd pyOS
pip install -e ".[dev]"
```

---

## Quick start

```python
# main.py
from pyos import Kernel, Screen

kernel = Kernel(arch="x86")

@kernel.on_boot
def main():
    Screen.clear()
    Screen.set_color("green", "black")
    Screen.print("Hello from pyOS!")
    Screen.print("Python DSL  ->  C kernel  ->  QEMU", row=2)

if __name__ == "__main__":
    kernel.build("myos.bin")
```

```bash
python main.py
pyos run myos.bin
```

Or with the CLI:

```bash
pyos build main.py -o myos.bin
pyos run myos.bin
pyos debug myos.bin
```

---

## CLI

| Command | Description |
|---------|-------------|
| `pyos check` | Verify gcc / nasm / qemu |
| `pyos new <name>` | Scaffold a new project |
| `pyos build <file.py> -o out.bin` | Build a bootable image |
| `pyos run <image.bin>` | Boot in QEMU |
| `pyos debug <image.bin>` | Headless serial log + panic translation |
| `pyos c <file.py> -o glue.c` | Inspect generated C glue |

---

## API overview

```python
from pyos import (
    Kernel, Screen, Keyboard, Memory,
    SysCall, Interrupts, GDT,
    File, Process,
    CapabilityError, UnsupportedOpError,
)
```

### Boot

```python
kernel = Kernel(arch="x86", heap_size=2*1024*1024)

@kernel.on_boot(priority=0)
def early():
    Screen.clear()
    Screen.print("booting...", row=0)

@kernel.on_boot(priority=1)
def later():
    ptr = Memory.malloc(256)
    Memory.memset(ptr, 0, 256)
    Memory.free(ptr)
```

### Keyboard & timer

```python
@kernel.on_keypress(mode="echo")
def on_key(key=None):
    pass  # enables IRQ1 path; shell handles lines

@kernel.on_timer(interval_ms=1000)
def tick():
    pass
```

### Files (build-time seeds)

```python
kernel = Kernel(arch="x86", enable_filesystem=True)
kernel.seed_file("motd.txt", "Welcome to pyOS\n")
```

Honest errors:

```python
# raises CapabilityError if filesystem is off
kernel.seed_file("x.txt", "nope")

# raises UnsupportedOpError / ValueError for bad ops / colors / non-ASCII VGA text
Screen.set_color("not_a_color")
Screen.print("عربي")  # VGA text is ASCII/CP437 only
```

---

## Capabilities (flags)

Enable real kernel subsystems with constructor flags:

```python
kernel = Kernel(
    arch="x86",
    stack_size=32768,
    heap_size=2 * 1024 * 1024,
    enable_interrupts=True,
    enable_paging=True,
    enable_user_mode=True,
    enable_processes=True,
    enable_filesystem=True,
    debug_level="lab",      # or "quiet"
    keypress_mode="echo",   # or "custom"
)
```

| Flag | Effect |
|------|--------|
| `enable_interrupts` | IDT + PIC + PIT + syscalls |
| `enable_paging` | Identity-map paging |
| `enable_user_mode` | GDT rings + TSS + stricter user copy |
| `enable_processes` | Task table + IRQ0 round-robin |
| `enable_filesystem` | VFS/ramfs + `seed_file` |

Inspect:

```python
print(kernel.get_info())
print(kernel.capabilities)
```

---

## Project layout

```text
pyos/
  api/          # Python DSL (Kernel, Screen, Memory, ...)
  build/        # codegen, toolchain, floppy builder
  boot/         # ASM bootloader
  kernel/       # freestanding C kernel
    arch/x86/   # GDT, IDT, PIC, paging, syscalls
    mm/         # heap, pmm
    drivers/    # VGA, keyboard, PIT, shell
    proc/       # tasks, ELF helper
    fs/         # VFS, ramfs, seed loader
    lib/        # debug, string
examples/
  basic/        # hello world, keyboard
  advanced/     # shell, full flags demo
  lab/          # probes (outputs gitignored)
tests/
  unit/
  integration/
docs/
  ARCHITECTURE.md
  ROADMAP.md
```

---

## Examples

```bash
python examples/basic/hello_world.py
python examples/basic/keyboard_input.py
python examples/advanced/shell_echo.py
python examples/advanced/advanced_os.py
```

---

## Guest shell

With `@kernel.on_keypress` enabled, type in the QEMU window:

| Command | Action |
|---------|--------|
| `help` | List commands |
| `ls` | List VFS files |
| `cat motd.txt` | Print a seeded file |
| `ps` | Show tasks |
| `free` | Heap hint |
| `clear` | Clear VGA |
| `echo hi` | Print text |

---

## Debugging

```bash
pyos debug myos.bin
```

Panics look like:

```text
========== pyOS PANIC ==========
Where : @kernel Screen.print
Why   : Print position is outside the VGA text screen (0..24 rows, 0..79 cols)
Hint  : Pass a valid row/col, or omit them to use the cursor
================================
```

Also emitted: `*.symbols.json` and linker `*.map` beside the image.

---

## Tests

```bash
pip install -e ".[dev]"
python -m pytest tests/ -q
```

Includes codegen honesty tests and QEMU serial smoke tests.

---

## Architecture

```text
┌─────────────┐     build-time      ┌─────────────┐
│  Python API │ ──────────────────► │  glue.c     │
└─────────────┘                     └──────┬──────┘
                                           │
┌─────────────┐                     ┌──────▼──────┐
│ bootloader  │ ──────────────────► │  C kernel   │
└─────────────┘                     └──────┬──────┘
                                           │
                                    ┌──────▼──────┐
                                    │  QEMU i386  │
                                    └─────────────┘
```

More detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Roadmap

Shipped in **1.0**: honest API, free-list heap, timer, syscalls, paging/GDT hooks, tasks, VFS, shell.

Next (Linux-like direction): per-process address spaces, `fork`/`exec`, ELF userland, virtio disk/net, x86_64.

See [docs/ROADMAP.md](docs/ROADMAP.md).

---

## Security notes

pyOS is a **lab / teaching / research** kernel:

- Default builds are still largely ring0-centric unless you enable user-mode flags
- Serial debug can leak EIP and boot traces (`debug_level="lab"`)
- Do not treat guest images as a hardened production OS

Report issues: [GitHub Issues](https://github.com/i87kxxz/pyOS/issues)

---

## Contributing

1. Fork & clone  
2. `pip install -e ".[dev]"`  
3. Keep the API **honest** (no silent stubs)  
4. Add tests for new codegen / QEMU behavior  
5. Open a PR

---

## License

MIT © 2026 i87kxxzz — see [LICENSE](LICENSE).
