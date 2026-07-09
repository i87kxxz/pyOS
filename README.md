# pyOS

**Build operating systems in Python.** You write a simple Python API; pyOS builds a real freestanding **C kernel** and an **ASM bootloader**, then runs it in QEMU.

```text
Your Python  →  C glue + C runtime  →  GCC -m32  ┐
                                                 ├→ os.bin → QEMU
ASM bootloader → NASM                            ┘
```

## Requirements (Windows)

| Tool | Role | Install |
|------|------|---------|
| **MinGW-w64 (GCC)** | Compile C runtime (`-m32`) | `winget install -e --id BrechtSanders.WinLibs.POSIX.UCRT` |
| **NASM** | Assemble bootloader | `winget install -e --id NASM.NASM` |
| **QEMU** | Run the OS | `winget install -e --id SoftwareFreedomConservancy.QEMU` |

Then verify:

```bash
pyos check
```

## Install pyOS

```bash
pip install -e .
```

## Hello World

```python
from pyos import Kernel, Screen

kernel = Kernel(arch="x86")

@kernel.on_boot
def main():
    Screen.clear()
    Screen.set_color("green", "black")
    Screen.print("Hello World!")

kernel.build("myos.bin")
```

```bash
pyos run myos.bin
pyos debug myos.bin   # human-readable serial log / panics
```

## Keyboard (runtime)

```python
@kernel.on_keypress
def on_key(key=None):
    pass  # enables IRQ1 echo in the C runtime
```

## Architecture

| Layer | What it does |
|-------|----------------|
| **Python API** | `Kernel`, `Screen`, decorators — records intent at build time |
| **C runtime** | VGA, keyboard, IDT/PIC, heap, syscalls, panic/serial |
| **ASM** | 16→32-bit bootloader only (`pyos/boot/bootloader.asm`) |

pyOS is **not** a full Python-to-machine-code compiler. Boot functions run once at build time; their `Screen.*` operations become C calls into the runtime.

## Human debug

Panics print clear messages on the serial port (and VGA):

```text
========== pyOS PANIC ==========
Where : @kernel Screen.print
Why   : Print position is outside the VGA text screen (0..24 rows, 0..79 cols)
Hint  : Pass a valid row/col, or omit them to use the cursor
Detail: EIP=0x....   (secondary technical detail)
================================
```

```bash
pyos debug myos.bin
```

## CLI

```bash
pyos check
pyos new myos
pyos build main.py -o myos.bin
pyos run myos.bin
pyos debug myos.bin
pyos c main.py -o glue.c    # inspect generated C glue
```

## Examples

```bash
python examples/hello_world.py
python examples/keyboard_input.py
python examples/advanced_os.py
```

## Tests

```bash
python -m pytest tests/ -q
```

## License

MIT
