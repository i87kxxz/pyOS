# Linux i386 ABI — acceptance checklist

Final gate for the pyOS Linux i386 ABI upgrade cycle (phases 0–6).
Run from repo root:

```bash
python -m pytest tests/ -q
```

All criteria below map to tests that must pass. See also
[`LINUX_ABI.md`](LINUX_ABI.md) for honest ABI limits.

| # | Criterion | Status | Covering tests |
|---|-----------|--------|----------------|
| 1 | `pyos` build produces Multiboot ELF bootable via `qemu -kernel` (no floppy 64-sector cap) | PASS | `test_build_multiboot_elf`, `test_build_allows_kernel_larger_than_floppy_limit`, `test_emulator_prefers_kernel_for_elf`, `test_qemu_boot_ok` |
| 2 | BusyBox/ash userland init + shell works (echo / uname) | PASS | `test_qemu_userland_shell`, `test_rootfs_includes_busybox_when_present` |
| 3 | fork + exec ELF i386 works | PASS | `test_qemu_fork_exec_elf`, `test_qemu_elf_write_exit`, `test_qemu_userland_shell` (fork-child/parent-ok), `test_elf_c_loader_symbols_present`, `test_linux_i386_syscall_numbers` |
| 4 | Files on ext2 via virtio-blk | PASS | `test_qemu_ext2_motd_from_disk`, `tests/unit/test_ext2_rootfs.py` |
| 5 | Network ping (or TCP) from guest works | PASS | `test_qemu_virtio_net_ping_gateway`, `test_network_codegen_flag`, `test_virtio_net_args` |
| 6 | `pytest tests/` green including QEMU integration | PASS | Full suite under `tests/` (unit + `tests/integration/test_qemu.py`) |
| 7 | Docs honestly state ABI limits | PASS | `test_linux_abi_docs_and_examples_present` → `docs/LINUX_ABI.md`, `examples/linux/` |
| — | Syscall ABI return (EAX restored after `int 0x80`) | PASS | `test_syscall_isr_stores_return_in_saved_eax`, `test_syscall_codegen_six_args` |
| — | Two-task schedule / page fault kill | PASS | `test_qemu_two_tasks_alternate` |
| — | DSL flags / codegen for Linux userland bundle | PASS | `test_linux_userland_codegen_bundle`, `test_linux_abi_default_and_reject_false`, `test_ext2_alias_enables_filesystem` |
| — | Kernel build disables SSE (no `#UD` in freestanding QEMU) | PASS | `test_kernel_cflags_disable_sse` |

## Gate verdict

**PASS** when `python -m pytest tests/ -q` reports all tests green and the
rows above remain mapped to those names.

Latest gate run: **45 passed**.

## Known remaining limitations (honest)

Documented in detail in [`LINUX_ABI.md`](LINUX_ABI.md) non-goals. Summary:

- Teaching / lab ABI — not a full Linux distribution (no glibc distro boot).
- fork address-space model is limited (page clone, not full COW); many syscalls are stubs or partial.
- BusyBox applet `fork+exec` via ash’s `busybox …` path is best-effort; tiny ELF fork+exec and ash’s own fork+wait are what the gate asserts.
- Networking is ICMP + socketcall subset (no general TCP server farm).
- No SMP, x86_64, UEFI, ext4/NFS, signals matching Linux, ASLR/NX/seccomp.
- Interactive shell input depends on guest stdin; automated demos drive serial output.
