# pyOS

**Version 1.0.1** — Build a real x86 operating system with a simple Python API.

You write readable Python (screens, handlers, feature flags).  
pyOS turns that into **C glue**, links it with a freestanding **C kernel**, and boots in **QEMU**.

```text
  You write Python (easy DSL)
           │
           ▼
  codegen → glue.c  +  C kernel  +  Multiboot
           │
           ▼
  GCC -m32 → myos.bin → QEMU (qemu -kernel)
```

**Important:** Python does **not** run inside the OS. It is a *build-time* language so you can describe the system easily. The guest that actually boots is C (+ a little ASM).

[![PyPI](https://img.shields.io/pypi/v/pyOS-kernel.svg)](https://pypi.org/project/pyOS-kernel/)
[![Python](https://img.shields.io/pypi/pyversions/pyOS-kernel.svg)](https://pypi.org/project/pyOS-kernel/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What's new in 1.0.1

Compared to 1.0.0, this release adds a much stronger kernel path:

| Area | What changed |
|------|----------------|
| **Boot** | Multiboot ELF via `qemu -kernel` (no tiny floppy size limit) |
| **Syscalls** | Linux **i386** numbers; `int 0x80` returns correctly in `EAX` (6 args) |
| **Processes** | Real context switch, paging helpers, page-fault handling |
| **ELF** | Real ELF32 load + `fork` / `execve` / `waitpid` subset |
| **Storage** | virtio-blk + **ext2** rootfs (`pyos mkrootfs`, `run --disk`) |
| **Network** | virtio-net + guest ping to QEMU gateway (`run --net`) |
| **Userland** | BusyBox static + ash `/init` shell on serial |
| **Docs / tests** | [LINUX_ABI.md](docs/LINUX_ABI.md), [ACCEPTANCE.md](docs/ACCEPTANCE.md), ~45 pytest tests |

Honest limits (not a full Linux distro): see [docs/LINUX_ABI.md](docs/LINUX_ABI.md).

---

## Table of contents

1. [How it works (Python vs C)](#how-it-works-python-vs-c)
2. [What is pyOS?](#what-is-pyos)
3. [What it is not](#what-it-is-not)
4. [Features](#features)
5. [Requirements](#requirements)
6. [Install](#install)
7. [Quick start](#quick-start)
8. [CLI](#cli)
9. [API overview](#api-overview)
10. [Capabilities (flags)](#capabilities-flags)
11. [Project layout](#project-layout)
12. [Examples](#examples)
13. [Guest shell (VGA)](#guest-shell-vga)
14. [Linux ABI userland](#linux-abi-userland-busybox--ash)
15. [Debugging](#debugging)
16. [Tests](#tests)
17. [Architecture](#architecture)
18. [Roadmap](#roadmap)
19. [Security notes](#security-notes)
20. [Contributing](#contributing)
21. [License](#license)

---

## How it works (Python vs C)

| You write | What actually boots |
|-----------|---------------------|
| Python DSL (`Kernel`, `Screen`, flags) | Freestanding **C kernel** in QEMU |
| `@kernel.on_boot` handlers on the **host** | Recorded ops become C calls in `glue.c` |

So: **Python = easy authoring**. **C = the real OS**. That is intentional — Python is high-level and cannot be a bare-metal kernel by itself.

Typical flow:

```bash
pip install pyOS-kernel
# write main.py with Kernel + Screen
pyos build main.py -o myos.bin
pyos run myos.bin
pyos debug myos.bin
```

---

## What is pyOS?

pyOS is a **Python DSL for building real OS kernels**.

| Layer | Role |
|-------|------|
| **Python** | Describe boot screens, handlers, and features at *build time* |
| **Codegen** | Emit honest C glue (no silent stubs) |
| **C kernel** | VGA, keyboard, heap, timer, IDT/PIC, Linux-ish syscalls, paging, tasks, VFS/ext2, virtio, shell |
| **ASM** | Early start / Multiboot entry (legacy floppy bootloader still present) |

---

## What it is not

- **Not** CPython running inside the kernel  
- **Not** a full Linux / glibc distro (no SMP, no ext4, no complete TCP stack)  
- **Not** Windows / WDK drivers  
- **Not** “fake” APIs: unsupported calls raise `CapabilityError` / `UnsupportedOpError`

Boot functions run on your **host** during `build()`. Only recorded operations become C calls in the guest.

It **does** speak a **Linux i386 syscall ABI** subset (BusyBox / ash on ext2 + virtio). See [docs/LINUX_ABI.md](docs/LINUX_ABI.md).

---

## Features

**Core**

- Freestanding **32-bit x86** Multiboot kernel (`qemu -kernel`)
- VGA text mode (`Screen.clear`, `print`, colors, cursor, scroll)
- PS/2 keyboard IRQ + optional echo / shell input
- PIT timer + `@kernel.on_timer`
- Human-readable **serial panics** (`pyos debug`)

**Memory & syscalls**

- Free-list **heap** (`malloc` / `free` / `calloc` / `realloc`)
- **Linux i386** syscall numbers by default (`fork`, `execve`, `write`, …) plus a few `PYOS_SYS_*` extensions
- Real **context switch** and page-fault kill path when processes/paging are enabled

**Security-oriented building blocks**

- Optional **GDT + TSS**
- Optional **paging** (identity map + per-task CR3 helpers)
- `copy_from_user` / range checks when `enable_user_mode=True`

**OS services**

- Process table + IRQ0 round-robin scheduling
- **VFS**: ramfs `seed_file(...)` and/or **ext2 on virtio-blk** (`mkrootfs` + `run --disk`)
- Optional **virtio-net** (`enable_network` + `run --net`) — guest can ping QEMU user-net gateway
- Guest **BusyBox/ash** userland path (see Linux ABI docs)
- Built-in **kernel shell** (VGA): `help`, `ls`, `cat`, `ps`, `free`, `clear`, `echo`

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
| `pyos run <image.bin> [--disk rootfs.img] [--net]` | Boot in QEMU (optional virtio disk/net) |
| `pyos mkrootfs -o rootfs.img` | Build a minimal ext2 rootfs (BusyBox/ash) |
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
    enable_filesystem=True,   # or enable_ext2=True
    enable_network=False,
    enable_linux_abi=True,    # default; cannot disable
    rootfs_path="rootfs.img", # metadata; still pass --disk to QEMU
    debug_level="lab",        # or "quiet"
    keypress_mode="echo",     # or "custom"
)
```

| Flag | Effect |
|------|--------|
| `enable_interrupts` | IDT + PIC + PIT + syscalls |
| `enable_paging` | Identity-map paging |
| `enable_user_mode` | GDT rings + TSS + stricter user copy |
| `enable_processes` | Task table + IRQ0 round-robin; `task_start_init()` |
| `enable_filesystem` / `enable_ext2` | VFS mount — ext2 via virtio-blk if `--disk`, else ramfs + `seed_file` |
| `enable_network` | `net_init()` / virtio-net (`run --net`) |
| `enable_linux_abi` | Linux i386 syscall numbers (always on) |
| `rootfs_path` | Recorded hint only; attach with `pyos run … --disk` |

Inspect:

```python
print(kernel.get_info())
print(kernel.capabilities)  # linux_abi, ext2, virtio_blk, virtio_net, …
```

---

## Project layout

```text
pyos/
  api/          # Python DSL (Kernel, Screen, Memory, ...)
  build/        # codegen, toolchain, rootfs builder
  boot/         # legacy ASM bootloader
  kernel/       # freestanding C kernel
    arch/x86/   # GDT, IDT, PIC, paging, syscalls, switch
    mm/         # heap, pmm
    drivers/    # VGA, keyboard, PIT, shell, virtio-blk/net, PCI
    proc/       # tasks, ELF loader
    fs/         # VFS, ramfs, ext2
    net/        # sockets + minimal IP/ICMP/TCP
    lib/        # debug, string
  user/         # tiny ELF / ash sources
examples/
  basic/        # hello world, keyboard
  advanced/     # shell, full flags demo
  linux/        # Linux ABI + BusyBox/ash
  lab/          # probes (outputs gitignored)
scripts/        # fetch BusyBox, build ash
third_party/    # BusyBox static + NOTICE
tests/
  unit/
  integration/
docs/
  ARCHITECTURE.md
  LINUX_ABI.md
  ACCEPTANCE.md
  ROADMAP.md
```

---

## Examples

```bash
python examples/basic/hello_world.py
python examples/basic/keyboard_input.py
python examples/advanced/shell_echo.py
python examples/advanced/advanced_os.py
python examples/linux/busybox_userland.py
```

---

## Guest shell (VGA)

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

## Linux ABI userland (BusyBox + ash)

```bash
# Fetch official BusyBox i386 static (GPL-2.0) — see third_party/NOTICE
python scripts/fetch_busybox.py
python scripts/build_ash.py

python -m pyos mkrootfs -o rootfs.img
python examples/linux/busybox_userland.py
python -m pyos run busybox_userland.bin --disk rootfs.img
```

Rootfs layout: `/init` (ash), `/bin/busybox`, `/bin/sh`, `/etc/motd`, `/dev` stubs, `/proc`.
On boot the kernel mounts ext2 and `execve`s `/init`. Details and non-goals: [docs/LINUX_ABI.md](docs/LINUX_ABI.md).

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

Includes codegen honesty tests and QEMU serial integration tests (boot, tasks, ELF, ext2, net, userland). Acceptance map: [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md).

---

## Architecture

```text
┌─────────────┐     build-time      ┌─────────────┐
│  Python API │ ──────────────────► │  glue.c     │
└─────────────┘                     └──────┬──────┘
                                           │
┌─────────────┐                     ┌──────▼──────┐
│ Multiboot   │ ──────────────────► │  C kernel   │
└─────────────┘                     └──────┬──────┘
                                           │
                                    ┌──────▼──────┐
                                    │  QEMU i386  │
                                    └─────────────┘
```

More detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Roadmap

**Shipped in 1.0.1:** honest API, heap, timer, **Linux i386 ABI**, paging/GDT, real tasks, VFS/ext2, virtio blk/net, BusyBox/ash userland, Multiboot boot.

Later (optional): richer address spaces, more complete sockets, x86_64.

See [docs/ROADMAP.md](docs/ROADMAP.md) and [docs/LINUX_ABI.md](docs/LINUX_ABI.md).

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

MIT © 2026 i87kxxz — see [LICENSE](LICENSE).
