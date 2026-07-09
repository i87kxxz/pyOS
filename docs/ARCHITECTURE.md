# pyOS Architecture

## Model

Python is a **build-time DSL**. It does not run inside the kernel.

```
Python API  ->  codegen (glue.c)  ->  freestanding C kernel  ->  QEMU
ASM bootloader (16->32) ------------^
```

## Layout

- `pyos/api/` — public Python surface (`Kernel`, `Screen`, …)
- `pyos/build/` — codegen, toolchain, floppy image builder
- `pyos/boot/` — MBR bootloader
- `pyos/kernel/` — C kernel (arch, mm, drivers, proc, fs, lib)

## Capabilities

Enable with `Kernel(...)` flags:

| Flag | Effect |
|------|--------|
| `enable_paging` | Identity-map 4MB + CR0.PG |
| `enable_user_mode` | GDT rings + TSS + stricter `copy_*_user` |
| `enable_processes` | Task table + IRQ0 round-robin |
| `enable_filesystem` | VFS/ramfs + seed files via `seed_file` |

Unsupported Python APIs raise `CapabilityError` / `UnsupportedOpError` at build time.
