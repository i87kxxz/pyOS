# pyOS Architecture

## Model

Python is a **build-time DSL**. It does not run inside the kernel.

```
Python API  ->  codegen (glue.c)  ->  freestanding C kernel  ->  QEMU
ASM bootloader (16->32) ------------^
```

## Layout

- `pyos/api/` — public Python surface (`Kernel`, `Screen`, …)
- `pyos/build/` — codegen, toolchain, floppy/Multiboot builder, ext2 rootfs
- `pyos/boot/` — MBR bootloader
- `pyos/kernel/` — C kernel (arch, mm, drivers, proc, fs, net, lib)
- `pyos/user/` — tiny ELF helpers + ash sources
- `examples/linux/` — Linux-ABI + BusyBox/ash demo

## Capabilities

Enable with `Kernel(...)` flags. Flags map to real C `KernelConfig` / boot glue.

| Flag | Effect |
|------|--------|
| `enable_paging` | Identity-map + CR0.PG |
| `enable_user_mode` | GDT rings + TSS + stricter `copy_*_user`; needed for `execve` |
| `enable_processes` | Task table + IRQ0 round-robin; glue calls `task_start_init()` |
| `enable_filesystem` / `enable_ext2` | `vfs_mount_root()` — virtio-blk + ext2 if QEMU `--disk`, else ramfs + `seed_file` |
| `enable_network` | Glue calls `net_init()` (virtio-net; use `pyos run --net`) |
| `enable_linux_abi` | Default **True**; Linux i386 syscall numbers (cannot disable) |
| `rootfs_path` | Metadata for `get_info()` / comments; disk still attached via `--disk` |

`kernel.capabilities` reflects the same (`linux_abi`, `ext2`, `virtio_blk`,
`virtio_net`, …). Unsupported Python APIs raise `CapabilityError` /
`UnsupportedOpError` at build time — no silent stubs.

## Linux ABI path

See [LINUX_ABI.md](LINUX_ABI.md) for syscall coverage, virtio, BusyBox/ash, and
explicit non-goals.
