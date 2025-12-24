# 🖥️ pyOS

**Build complete operating systems using Python.** Write your OS kernel in Python, and pyOS compiles it to Assembly and Machine Code that runs on real hardware.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

<p align="center">
  <img src="https://raw.githubusercontent.com/pyos/pyos/main/docs/screenshot.png" alt="pyOS Screenshot" width="600">
</p>

## ✨ Features

- 🐍 **Write OS in Pure Python** - No Assembly knowledge required
- ⚡ **Compiles to Native Code** - Python → Assembly → Machine Code
- 🎨 **VGA Text Mode** - Full color support (16 colors)
- ⌨️ **Keyboard Support** - PS/2 keyboard driver included
- 🧠 **Memory Management** - GDT, heap allocation, stack management
- 🔧 **QEMU Integration** - Test your OS instantly
- 📦 **Easy Installation** - `pip install pyOS`

## 🚀 Quick Start

### Installation

```bash
pip install pyOS
```

**Requirements:** NASM and QEMU
```bash
# Windows (with chocolatey)
choco install nasm qemu

# Linux
sudo apt install nasm qemu-system-x86

# macOS
brew install nasm qemu
```

### Hello World OS

```python
from pyos import Kernel, Screen

kernel = Kernel(arch="x86")

@kernel.on_boot
def main():
    Screen.clear()
    Screen.set_color("green", "black")
    Screen.print("Hello World!")
    Screen.print("Welcome to my OS!", row=1)

kernel.build("myos.iso")
```

### Run Your OS

```bash
qemu-system-i386 -fda myos.iso
```

## 📖 Documentation

### Kernel

```python
from pyos import Kernel

# Create a kernel targeting x86 architecture
kernel = Kernel(
    arch="x86",           # or "x86_64"
    stack_size=16384,     # 16KB stack
    heap_size=1048576,    # 1MB heap
)

# Register boot functions with priority (lower = runs first)
@kernel.on_boot(priority=0)
def early_boot():
    pass

@kernel.on_boot(priority=1)
def late_boot():
    pass
```

### Screen (VGA Text Mode)

```python
from pyos import Screen

# Clear screen
Screen.clear()

# Set default colors
Screen.set_color("white", "blue")

# Print text
Screen.print("Hello!")
Screen.print("At position", row=5, col=10)
Screen.print("Colored text", color="red", background="black")

# Available colors:
# black, blue, green, cyan, red, magenta, brown, light_gray,
# dark_gray, light_blue, light_green, light_cyan, light_red,
# light_magenta, yellow, white
```

### Building & Running

```python
# Build ISO image
kernel.build("myos.iso")

# Or build raw binary
kernel.build("myos.bin", format="bin")

# Generate Assembly only (for inspection)
asm_code = kernel.compile()
```

## 🎯 Examples

### Multi-Stage Boot

```python
from pyos import Kernel, Screen

kernel = Kernel(arch="x86")

@kernel.on_boot(priority=0)
def init():
    Screen.clear()
    Screen.print("Initializing...", color="cyan")

@kernel.on_boot(priority=1)
def load_drivers():
    Screen.print("[OK] Drivers loaded", row=1, color="green")

@kernel.on_boot(priority=2)
def ready():
    Screen.print("System Ready!", row=3, color="yellow")

kernel.build("myos.iso")
```

### Colorful UI

```python
from pyos import Kernel, Screen

kernel = Kernel(arch="x86")

@kernel.on_boot
def main():
    Screen.clear()
    
    # Draw a header
    Screen.set_color("white", "blue")
    Screen.print("=" * 40, row=0)
    Screen.print("       My Operating System v1.0", row=1)
    Screen.print("=" * 40, row=2)
    
    # System info
    Screen.set_color("green", "black")
    Screen.print("[OK] CPU initialized", row=4)
    Screen.print("[OK] Memory ready", row=5)
    
    # Footer
    Screen.set_color("yellow", "black")
    Screen.print("Press any key to continue...", row=10)

kernel.build("myos.iso")
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Your Python Code                      │
│   @kernel.on_boot                                        │
│   def main():                                            │
│       Screen.print("Hello!")                             │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   pyOS Compiler                          │
│   • Parses Python code                                   │
│   • Captures screen/keyboard operations                  │
│   • Generates x86 Assembly                               │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   NASM Assembler                         │
│   • Converts Assembly to Machine Code                    │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   Bootable Image                         │
│   • Bootloader (512 bytes)                               │
│   • Kernel binary                                        │
│   • Runs on QEMU or real hardware                        │
└─────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
pyOS/
├── pyos/
│   ├── __init__.py
│   ├── kernel.py           # Kernel class and decorators
│   ├── builder.py          # ISO/binary builder
│   ├── emulator.py         # QEMU integration
│   ├── cli.py              # Command-line interface
│   ├── compiler/
│   │   ├── codegen.py      # Python → Assembly
│   │   └── assembler.py    # Assembly → Machine Code
│   ├── drivers/
│   │   ├── screen.py       # VGA text mode driver
│   │   └── keyboard.py     # PS/2 keyboard driver
│   ├── memory/
│   │   ├── manager.py      # Memory allocation
│   │   └── gdt.py          # Global Descriptor Table
│   └── boot/
│       └── bootloader.asm  # x86 bootloader
└── examples/
    ├── hello_world.py
    ├── keyboard_input.py
    └── advanced_os.py
```

## 🛠️ CLI Commands

```bash
# Create new project
pyos new myos

# Build OS
pyos build main.py -o myos.iso

# Run in QEMU
pyos run myos.iso

# Debug mode
pyos debug myos.iso

# Generate Assembly only
pyos asm main.py -o kernel.asm

# Check dependencies
pyos check
```

## 🤝 Contributing

Contributions are welcome! Feel free to:

- 🐛 Report bugs
- 💡 Suggest features
- 🔧 Submit pull requests

## 📄 License

MIT License - feel free to use in your own projects!

## 🙏 Acknowledgments

- NASM - The Netwide Assembler
- QEMU - Open source machine emulator
- OSDev Wiki - Invaluable OS development resources

---

<p align="center">
  Made with ❤️ for OS enthusiasts
</p>

<p align="center">
  <b>Build your dream OS with Python!</b>
</p>
