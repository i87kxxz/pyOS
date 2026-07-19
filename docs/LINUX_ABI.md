# Linux ABI on pyOS

Honest documentation of what the guest kernel exposes to **Linux i386 ELF**
userland (BusyBox static, pyOS ash `/init`). This is a teaching / lab ABI, not
a Linux distribution.

## Default ABI

Syscall numbers match **Linux i386** (`arch/x86/entry/syscalls/syscall_32.tbl`).
The Python flag `enable_linux_abi=True` is the default and **cannot be turned
off** — there is no alternate numbering scheme.

```python
from pyos import Kernel, SysCallNumber

kernel = Kernel(
    arch="x86",
    enable_paging=True,
    enable_user_mode=True,
    enable_processes=True,
    enable_filesystem=True,  # or enable_ext2=True
    enable_linux_abi=True,   # default
)
assert SysCallNumber.SYS_WRITE.value == 4
```

Legacy pyOS-only calls remain under `PYOS_SYS_*` (high numbers) for the DSL /
kernel demos; they are not part of the Linux table.

## Kernel flags → runtime

| Python flag | C / QEMU effect |
|-------------|-----------------|
| `enable_paging` | Identity map + CR0.PG |
| `enable_user_mode` | GDT rings + TSS + stricter `copy_*_user`; required for `execve` |
| `enable_processes` | Task table; `task_start_init()` from glue |
| `enable_filesystem` / `enable_ext2` | `vfs_mount_root()` — virtio-blk + ext2 if `--disk`, else ramfs seeds |
| `enable_network` | `net_init()` — virtio-net (use `pyos run --net`) |
| `rootfs_path` | Metadata only (shown in `get_info()` / glue comments); attach via `--disk` |
| `enable_linux_abi` | Always on; documents Linux i386 numbers |

Capabilities dict mirrors these (`linux_abi`, `ext2`, `virtio_blk`, `virtio_net`, …).
Disabled features raise `CapabilityError` / `UnsupportedOpError` — no silent stubs.

## Booting userland

```bash
python scripts/fetch_busybox.py
python scripts/build_ash.py
python -m pyos mkrootfs -o rootfs.img

# Build an image with the flags above (see examples/linux/)
python examples/linux/busybox_userland.py
python -m pyos run busybox_userland.bin --disk rootfs.img
# optional NIC:
python -m pyos run busybox_userland.bin --disk rootfs.img --net
```

Rootfs layout (when userland is included): `/init` (ash), `/bin/busybox`,
`/bin/sh`, `/etc/motd`, `/dev` stubs, `/proc`. On boot the kernel mounts ext2
and `execve`s `/init`.

## Supported syscalls (practical)

Implemented enough for BusyBox/ash demos. Many return stubs / partial results.

| Number | Name | Notes |
|--------|------|--------|
| 1 | `exit` / `exit_group` | Halts / task exit |
| 2 | `fork` | Copy task; limited address-space model |
| 3 | `read` | stdin / VFS / ext2 |
| 4 | `write` | stdout→serial/VGA; VFS write |
| 5 / 295 | `open` / `openat` | Path open; `O_CREAT` on ext2 |
| 6 | `close` | FD close |
| 7 / 114 | `waitpid` / `wait4` | Basic wait |
| 11 | `execve` | ELF32 ET_EXEC load |
| 12 | `chdir` | Process cwd string |
| 13 | `time` | PIT-based |
| 20 | `getpid` | |
| 33 / 307 | `access` / `faccessat` | Path exists check |
| 41 / 63 | `dup` / `dup2` | Minimal |
| 42 | `pipe` | Minimal |
| 45 | `brk` | Heap break for user |
| 24/47/49/50 | `getuid` / `getgid` / `geteuid` / `getegid` | Return 0 |
| 54 | `ioctl` | Limited (TTY-ish stubs) |
| 55 | `fcntl` | Stub |
| 64 | `getppid` | |
| 82 / 168 | `select` / `poll` | Partial |
| 90 / 192 | `mmap` / `mmap2` | Limited mapping |
| 91 | `munmap` | |
| 102 | `socketcall` | Virtio-net path when network enabled |
| 106–108 | `stat` / `lstat` / `fstat` | Partial |
| 109 | `uname` | Fixed `pyOS` / `i386` strings |
| 125 | `mprotect` | Stub OK |
| 141 / 220 | `getdents` / `getdents64` | Directory listing |
| 158 | `sched_yield` | |
| 162 | `nanosleep` | |
| 174 / 175 | `rt_sigaction` / `rt_sigprocmask` | Stub OK |
| 183 | `getcwd` | |
| 191 | `ugetrlimit` | Stub |
| 243 | `set_thread_area` | Stub OK (BusyBox TLS) |
| 252 | `exit_group` | Same as exit |

Exact behavior is in `pyos/kernel/arch/x86/syscall.c`. Treat anything not
exercised by ash/BusyBox demos as **best-effort**.

## Virtio

| Device | When | QEMU |
|--------|------|------|
| **virtio-blk** | `enable_filesystem` / `enable_ext2` + `vfs_mount_root` | `pyos run … --disk rootfs.img` |
| **virtio-net** | `enable_network` + `net_init` | `pyos run … --net` |

PCI legacy virtio (disable-modern) is used so the freestanding driver stays small.

## Non-goals

Explicitly **out of scope** for this ABI path:

- Full **glibc** / Debian / Alpine distro boot
- **SMP**, preemption beyond IRQ0 round-robin
- **x86_64**, long mode, UEFI
- Complete Linux VFS (no ext4, no NFS, no FUSE)
- Full networking stack (no TCP listen server farm; ICMP/socketcall subset only)
- Signal delivery semantics matching Linux
- ASLR, NX enforcement, seccomp, cgroups, namespaces
- CPython or other interpreters inside the kernel
- Silent stub APIs in the Python DSL

## Related

- Example: [`examples/linux/`](../examples/linux/)
- Architecture notes: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Roadmap: [`ROADMAP.md`](ROADMAP.md)
