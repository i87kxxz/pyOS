# pyOS Beginner Guide

This guide takes you from installation to your first working operating system with as few steps as possible.

## 1. Installation

Install Python 3.8 or newer, MinGW-w64 with `-m32` support, NASM, and QEMU.
On Windows, install the tools from PowerShell:

```powershell
winget install -e --id BrechtSanders.WinLibs.POSIX.UCRT
winget install -e --id NASM.NASM
winget install -e --id SoftwareFreedomConservancy.QEMU
```

Then open a new terminal window:

```powershell
python -m pip install -e ".[dev]"
pyos check
```

If `[OK]` appears next to GCC, NASM, and QEMU, you are ready. The `pyos check` command explains which tools are missing and how to fix them.

## 2. Your First Project

Create a ready-to-use project:

```powershell
pyos new hello
cd hello
pyos build main.py -o hello.bin
pyos run hello.bin
```

To run without opening a QEMU window, or to stop automatically:

```powershell
pyos run hello.bin --headless --timeout 5
```

## 3. Understand the Architecture

Python is a build-time description language. Python does not run inside the guest OS; your commands are converted into C, which is then built into a kernel that runs inside QEMU.

To inspect the generated C code:

```powershell
pyos c main.py -o glue.c
```

## 4. Testing

The fast tests run immediately:

```powershell
python -m pytest -q
```

Real QEMU tests are optional because they require the external toolchain and take longer:

```powershell
$env:PYOS_RUN_QEMU="1"
python -m pytest -q
```

## Common Issues

- `GCC cannot compile with -m32`: install a MinGW-w64 distribution that includes 32-bit libraries.
- `QEMU not found`: close and reopen the terminal after installing QEMU.
- Do not run `pyos run` until `pyos build` completes successfully.
- Start with `examples/basic` before trying networking or ext2.
