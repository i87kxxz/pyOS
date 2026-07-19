"""
Linux-ABI userland image — BusyBox/ash on ext2 via virtio-blk.

Builds a Multiboot ELF kernel with paging, user mode, processes, and
filesystem (ext2). Optionally enable virtio-net with enable_network=True.

Usage
-----
# 1) Fetch / build userland binaries (once)
python scripts/fetch_busybox.py
python scripts/build_ash.py

# 2) Create an ext2 rootfs with /init (ash) + /bin/busybox
python -m pyos mkrootfs -o rootfs.img

# 3) Build this kernel
python examples/linux/busybox_userland.py

# 4) Boot with the disk attached (and optional --net)
python -m pyos run busybox_userland.bin --disk rootfs.img
# python -m pyos run busybox_userland.bin --disk rootfs.img --net

See docs/LINUX_ABI.md for supported syscalls and non-goals.
"""

from pyos import Kernel, Screen

# rootfs_path is metadata for get_info() / Kernel.run(); QEMU still needs --disk
# (or pass disk= to Kernel.run) because the image is not baked into the ELF.
kernel = Kernel(
    arch="x86",
    heap_size=4 * 1024 * 1024,
    enable_paging=True,
    enable_user_mode=True,
    enable_processes=True,
    enable_filesystem=True,  # alias: enable_ext2=True
    enable_linux_abi=True,  # default; Linux i386 syscall numbers
    rootfs_path="rootfs.img",
    # enable_network=True,  # uncomment + pass --net to QEMU for virtio-net
    debug_level="lab",
)


@kernel.on_boot
def banner():
    Screen.clear()
    Screen.set_color("light_cyan", "black")
    Screen.print("pyOS Linux ABI", row=0)
    Screen.print("paging+user+proc+ext2", row=1)
    Screen.print("attach rootfs: --disk", row=2)


if __name__ == "__main__":
    out = kernel.build("busybox_userland.bin")
    print(f"Built {out}")
    print("Next:")
    print("  python -m pyos mkrootfs -o rootfs.img")
    print("  python -m pyos run busybox_userland.bin --disk rootfs.img")
    print("Capabilities:", kernel.capabilities)
