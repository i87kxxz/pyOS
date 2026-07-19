# pyOS Roadmap

## Shipped (Phases 0–5)

1. Honest Python DSL + package layout
2. Heap free-list, screen, stack_size, PIT, keyboard
3. Linux i386 syscall numbers + ELF `execve` / `fork` subset
4. GDT/TSS, paging, usercopy
5. Processes (IRQ0 RR) + page-fault kill path
6. VFS: ramfs seeds + **ext2 on virtio-blk**
7. Virtio-net + ICMP / `socketcall` subset
8. BusyBox static + ash `/init` userland (`mkrootfs`, `run --disk`)
9. Tests (unit + QEMU integration) + docs

## Phase 6 (API honesty)

Python flags, codegen comments, `examples/linux/`, and docs
([LINUX_ABI.md](LINUX_ABI.md)) expose the above without marketing fluff.

## Later (optional)

- Richer per-process address spaces / COW
- More complete socket + block drivers
- x86_64 (separate effort)

## Out of scope

Full glibc distro, SMP, GPU, UEFI, CPython-in-kernel, silent stub APIs.
See [LINUX_ABI.md](LINUX_ABI.md) non-goals.
