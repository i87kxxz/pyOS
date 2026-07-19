# Linux ABI examples

Minimal kernels aimed at the **Linux i386 syscall ABI** path (BusyBox / ash
userland on an ext2 rootfs).

| File | What it builds |
|------|----------------|
| `busybox_userland.py` | paging + user_mode + processes + filesystem/ext2 |

## Quick path

```bash
python scripts/fetch_busybox.py   # optional; ash alone still boots
python scripts/build_ash.py

python -m pyos mkrootfs -o rootfs.img
python examples/linux/busybox_userland.py
python -m pyos run busybox_userland.bin --disk rootfs.img
```

Serial should show ext2 mount, `/init` exec, BusyBox banner / `# ` prompt.

Full details: [docs/LINUX_ABI.md](../../docs/LINUX_ABI.md).
