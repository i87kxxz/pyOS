"""
Create a minimal ext2 disk image for pyOS (no mke2fs required).

Layout (1 KiB or 4 KiB blocks):
  block 0     unused / boot (or start of FS for 4K)
  superblock at byte offset 1024
  group descriptor, bitmaps, inode table, then data

Phase 5 rootfs includes /bin/busybox, /init (ash), /etc, /dev stubs.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

EXT2_MAGIC = 0xEF53
EXT2_ROOT_INO = 2
EXT2_S_IFDIR = 0x4000
EXT2_S_IFREG = 0x8000
EXT2_FT_REG = 1
EXT2_FT_DIR = 2

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BUSYBOX_CANDIDATES = [
    _REPO_ROOT / "third_party" / "busybox-i386-static",
    _REPO_ROOT / "third_party" / "busybox",
]
_ASH_CANDIDATES = [
    _REPO_ROOT / "third_party" / "ash-i386",
    _REPO_ROOT / "third_party" / "ash",
]


def _align4(n: int) -> int:
    return (n + 3) & ~3


def find_busybox() -> Optional[Path]:
    for p in _BUSYBOX_CANDIDATES:
        if p.is_file() and p.stat().st_size > 1000:
            return p
    return None


def find_ash() -> Optional[Path]:
    for p in _ASH_CANDIDATES:
        if p.is_file() and p.stat().st_size > 100:
            return p
    return None


class Ext2Builder:
    def __init__(self, size_bytes: int = 4 * 1024 * 1024, block_size: int = 4096):
        if block_size not in (1024, 2048, 4096):
            raise ValueError("block_size must be 1024, 2048, or 4096")
        if size_bytes < block_size * 64:
            raise ValueError("image too small")
        self.block_size = block_size
        self.size = size_bytes - (size_bytes % block_size)
        self.blocks_count = self.size // block_size
        self.inode_size = 128
        self.inodes_count = 256
        self.inodes_per_group = self.inodes_count
        self.blocks_per_group = self.blocks_count
        self.first_data_block = 1 if block_size == 1024 else 0
        self.ptrs_per_block = block_size // 4

        self.gd_block = self.first_data_block + 1
        self.block_bitmap = self.gd_block + 1
        self.inode_bitmap = self.block_bitmap + 1
        inode_table_bytes = self.inodes_count * self.inode_size
        self.inode_table_blocks = (inode_table_bytes + block_size - 1) // block_size
        self.inode_table = self.inode_bitmap + 1
        self.data_start = self.inode_table + self.inode_table_blocks

        self.img = bytearray(self.size)
        self.block_used = [False] * self.blocks_count
        self.inode_used = [False] * (self.inodes_count + 1)
        self.next_ino = 11

        for b in range(self.data_start):
            if b < self.blocks_count:
                self.block_used[b] = True
        for i in range(1, 11):
            self.inode_used[i] = True

    def _blk_off(self, block: int) -> int:
        return block * self.block_size

    def _write_block(self, block: int, data: bytes) -> None:
        off = self._blk_off(block)
        raw = bytearray(self.block_size)
        raw[: min(len(data), self.block_size)] = data[: self.block_size]
        self.img[off : off + self.block_size] = raw

    def _read_block(self, block: int) -> bytearray:
        off = self._blk_off(block)
        return bytearray(self.img[off : off + self.block_size])

    def _alloc_block(self) -> int:
        for b in range(self.data_start, self.blocks_count):
            if not self.block_used[b]:
                self.block_used[b] = True
                self._write_block(b, b"\x00" * self.block_size)
                return b
        raise RuntimeError("out of blocks")

    def _alloc_inode(self) -> int:
        ino = self.next_ino
        while ino <= self.inodes_count and self.inode_used[ino]:
            ino += 1
        if ino > self.inodes_count:
            raise RuntimeError("out of inodes")
        self.inode_used[ino] = True
        self.next_ino = ino + 1
        return ino

    def _pack_inode(self, mode: int, size: int, links: int, blocks: List[int]) -> bytes:
        i_blocks = (len(blocks) * self.block_size) // 512
        i_block = [0] * 15
        direct = blocks[:12]
        for i, b in enumerate(direct):
            i_block[i] = b
        rest = blocks[12:]
        if rest:
            # single indirect
            ind = self._alloc_block()
            i_block[12] = ind
            i_blocks += self.block_size // 512
            ptrs = bytearray(self.block_size)
            if len(rest) > self.ptrs_per_block:
                # double indirect for overflow past single
                single_cap = self.ptrs_per_block
                single_part = rest[:single_cap]
                for i, b in enumerate(single_part):
                    struct.pack_into("<I", ptrs, i * 4, b)
                self._write_block(ind, bytes(ptrs))

                dbl_rest = rest[single_cap:]
                dbl = self._alloc_block()
                i_block[13] = dbl
                i_blocks += self.block_size // 512
                dbl_ptrs = bytearray(self.block_size)
                di = 0
                pos = 0
                while pos < len(dbl_rest):
                    leaf = self._alloc_block()
                    i_blocks += self.block_size // 512
                    leaf_buf = bytearray(self.block_size)
                    chunk = dbl_rest[pos : pos + self.ptrs_per_block]
                    for j, b in enumerate(chunk):
                        struct.pack_into("<I", leaf_buf, j * 4, b)
                    self._write_block(leaf, bytes(leaf_buf))
                    struct.pack_into("<I", dbl_ptrs, di * 4, leaf)
                    di += 1
                    pos += self.ptrs_per_block
                    if di >= self.ptrs_per_block:
                        raise RuntimeError("file too large for double indirect")
                self._write_block(dbl, bytes(dbl_ptrs))
            else:
                for i, b in enumerate(rest):
                    struct.pack_into("<I", ptrs, i * 4, b)
                self._write_block(ind, bytes(ptrs))

        buf = bytearray(self.inode_size)
        struct.pack_into("<H", buf, 0, mode & 0xFFFF)
        struct.pack_into("<H", buf, 2, 0)
        struct.pack_into("<I", buf, 4, size)
        struct.pack_into("<I", buf, 8, 0)
        struct.pack_into("<I", buf, 12, 0)
        struct.pack_into("<I", buf, 16, 0)
        struct.pack_into("<I", buf, 20, 0)
        struct.pack_into("<H", buf, 24, 0)
        struct.pack_into("<H", buf, 26, links)
        struct.pack_into("<I", buf, 28, i_blocks)
        struct.pack_into("<I", buf, 32, 0)
        struct.pack_into("<I", buf, 36, 0)
        for i in range(15):
            struct.pack_into("<I", buf, 40 + i * 4, i_block[i])
        return bytes(buf)

    def _write_inode(self, ino: int, blob: bytes) -> None:
        index = ino - 1
        byte_off = index * self.inode_size
        block = self.inode_table + (byte_off // self.block_size)
        off = self._blk_off(block) + (byte_off % self.block_size)
        self.img[off : off + self.inode_size] = blob[: self.inode_size]

    def _dir_entries_block(self, entries: List[Tuple[int, str, int]]) -> bytes:
        buf = bytearray(self.block_size)
        pos = 0
        for i, (ino, name, ftype) in enumerate(entries):
            name_b = name.encode("ascii")
            rec = _align4(8 + len(name_b))
            if i == len(entries) - 1:
                rec = self.block_size - pos
            struct.pack_into("<IHBB", buf, pos, ino, rec, len(name_b), ftype)
            buf[pos + 8 : pos + 8 + len(name_b)] = name_b
            pos += rec
        return bytes(buf)

    def mkdir(self, parent_ino: int, name: str) -> int:
        if name == "/":
            ino = EXT2_ROOT_INO
            self.inode_used[ino] = True
        else:
            ino = self._alloc_inode()
        block = self._alloc_block()
        entries = [
            (ino, ".", EXT2_FT_DIR),
            (parent_ino if name != "/" else ino, "..", EXT2_FT_DIR),
        ]
        self._write_block(block, self._dir_entries_block(entries))
        mode = EXT2_S_IFDIR | 0o755
        self._write_inode(ino, self._pack_inode(mode, self.block_size, 2, [block]))
        if name != "/":
            self._dir_add(parent_ino, ino, name, EXT2_FT_DIR)
            self._bump_links(parent_ino, 1)
        return ino

    def _bump_links(self, ino: int, delta: int) -> None:
        index = ino - 1
        byte_off = index * self.inode_size
        block = self.inode_table + (byte_off // self.block_size)
        off = self._blk_off(block) + (byte_off % self.block_size)
        links = struct.unpack_from("<H", self.img, off + 26)[0]
        struct.pack_into("<H", self.img, off + 26, links + delta)

    def _dir_add(self, dir_ino: int, child: int, name: str, ftype: int) -> None:
        index = dir_ino - 1
        byte_off = index * self.inode_size
        iblock = self.inode_table + (byte_off // self.block_size)
        ioff = self._blk_off(iblock) + (byte_off % self.block_size)
        data_block = struct.unpack_from("<I", self.img, ioff + 40)[0]
        blk = self._read_block(data_block)
        pos = 0
        last_pos = 0
        while pos < self.block_size:
            ino, rec, nlen, _ft = struct.unpack_from("<IHBB", blk, pos)
            if rec < 8:
                break
            last_pos = pos
            if pos + rec >= self.block_size:
                break
            pos += rec
        ino, rec, nlen, _ft = struct.unpack_from("<IHBB", blk, last_pos)
        ideal = _align4(8 + nlen) if ino else 0
        need = _align4(8 + len(name))
        if ideal + need > rec:
            raise RuntimeError(f"directory block full for {name}")
        struct.pack_into("<H", blk, last_pos + 4, ideal)
        new_pos = last_pos + ideal
        name_b = name.encode("ascii")
        struct.pack_into("<IHBB", blk, new_pos, child, rec - ideal, len(name_b), ftype)
        blk[new_pos + 8 : new_pos + 8 + len(name_b)] = name_b
        self._write_block(data_block, bytes(blk))

    def create_file(self, parent_ino: int, name: str, data: bytes, mode: int = 0o644) -> int:
        ino = self._alloc_inode()
        blocks: List[int] = []
        offset = 0
        if not data:
            # empty file — still ok with zero blocks
            pass
        else:
            while offset < len(data):
                b = self._alloc_block()
                chunk = data[offset : offset + self.block_size]
                self._write_block(b, chunk)
                blocks.append(b)
                offset += self.block_size
        full_mode = EXT2_S_IFREG | (mode & 0o777)
        self._write_inode(ino, self._pack_inode(full_mode, len(data), 1, blocks))
        self._dir_add(parent_ino, ino, name, EXT2_FT_REG)
        return ino

    def finalize(self) -> bytes:
        bb = bytearray(self.block_size)
        for b, used in enumerate(self.block_used):
            if used:
                bb[b // 8] |= 1 << (b % 8)
        self._write_block(self.block_bitmap, bytes(bb))

        ib = bytearray(self.block_size)
        for i in range(1, self.inodes_count + 1):
            if self.inode_used[i]:
                bit = i - 1
                ib[bit // 8] |= 1 << (bit % 8)
        self._write_block(self.inode_bitmap, bytes(ib))

        free_blocks = sum(1 for u in self.block_used if not u)
        free_inodes = sum(
            1 for i in range(1, self.inodes_count + 1) if not self.inode_used[i]
        )

        gd = bytearray(self.block_size)
        struct.pack_into(
            "<IIIHHH",
            gd,
            0,
            self.block_bitmap,
            self.inode_bitmap,
            self.inode_table,
            free_blocks,
            free_inodes,
            3,
        )
        self._write_block(self.gd_block, bytes(gd))

        sb = bytearray(1024)
        log_bs = {1024: 0, 2048: 1, 4096: 2}[self.block_size]
        struct.pack_into(
            "<IIIIII",
            sb,
            0,
            self.inodes_count,
            self.blocks_count,
            0,
            free_blocks,
            free_inodes,
            self.first_data_block,
        )
        struct.pack_into("<II", sb, 24, log_bs, 0)
        struct.pack_into(
            "<III",
            sb,
            32,
            self.blocks_per_group,
            self.blocks_per_group,
            self.inodes_per_group,
        )
        struct.pack_into("<H", sb, 56, EXT2_MAGIC)
        struct.pack_into("<H", sb, 58, 1)
        struct.pack_into("<I", sb, 76, 1)
        struct.pack_into("<I", sb, 84, 11)
        struct.pack_into("<H", sb, 88, self.inode_size)
        self.img[1024 : 1024 + 1024] = sb
        return bytes(self.img)


def ensure_ash_binary() -> Optional[Path]:
    """Return ash path, rebuilding if missing or older than ash.c."""
    existing = find_ash()
    ash_src = _REPO_ROOT / "pyos" / "user" / "ash.c"
    needs_build = existing is None
    if existing and ash_src.is_file():
        try:
            if ash_src.stat().st_mtime > existing.stat().st_mtime:
                needs_build = True
        except OSError:
            needs_build = True
    if not needs_build:
        return existing
    try:
        from scripts.build_ash import build_ash_elf  # type: ignore

        return build_ash_elf()
    except Exception:
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "build_ash", _REPO_ROOT / "scripts" / "build_ash.py"
            )
            if not spec or not spec.loader:
                return existing
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.build_ash_elf()
        except Exception:
            return existing


def create_rootfs(
    path: Union[str, Path],
    motd: str = "Welcome to pyOS\n",
    size_bytes: int = 4 * 1024 * 1024,
    extra_files: Optional[Dict[str, bytes]] = None,
    include_userland: bool = True,
) -> Path:
    """Create rootfs.img with /etc/motd, /bin, optional BusyBox + ash init."""
    path = Path(path)
    # Prefer 4KiB blocks so a ~1MiB BusyBox fits in single-indirect range.
    block_size = 4096
    need = size_bytes
    busybox_data: Optional[bytes] = None
    ash_data: Optional[bytes] = None

    if include_userland:
        bb = find_busybox()
        if bb:
            busybox_data = bb.read_bytes()
        need = max(need, len(busybox_data) + 3 * 1024 * 1024)
        ash_path = ensure_ash_binary()
        if ash_path:
            ash_data = ash_path.read_bytes()
            need = max(need, len(ash_data) + 512 * 1024)

    b = Ext2Builder(size_bytes=need, block_size=block_size)
    root = b.mkdir(EXT2_ROOT_INO, "/")
    etc = b.mkdir(root, "etc")
    bin_ino = b.mkdir(root, "bin")
    dev = b.mkdir(root, "dev")
    proc = b.mkdir(root, "proc")
    b.create_file(etc, "motd", motd.encode("ascii"))
    inittab = (
        "# pyOS inittab (BusyBox init)\n"
        "::sysinit:/bin/busybox mount -t proc proc /proc\n"
        "::askfirst:-/bin/sh\n"
    )
    b.create_file(etc, "inittab", inittab.encode("ascii"))
    b.create_file(etc, "hostname", b"pyos\n")
    # Placeholder device nodes as empty files (VFS provides /dev/null etc.).
    b.create_file(dev, "null", b"")
    b.create_file(dev, "zero", b"")
    b.create_file(dev, "console", b"")
    b.create_file(dev, "tty", b"")
    b.create_file(proc, ".keep", b"")

    if busybox_data:
        b.create_file(bin_ino, "busybox", busybox_data, mode=0o755)
    else:
        b.create_file(bin_ino, ".keep", b"")

    if ash_data:
        # /init and /bin/sh are the ash shell; BusyBox remains at /bin/busybox.
        b.create_file(root, "init", ash_data, mode=0o755)
        b.create_file(bin_ino, "sh", ash_data, mode=0o755)
        b.create_file(bin_ino, "ash", ash_data, mode=0o755)
    elif busybox_data:
        # Fallback: boot BusyBox directly as init.
        b.create_file(root, "init", busybox_data, mode=0o755)

    if extra_files:
        for fpath, data in extra_files.items():
            parts = [p for p in fpath.split("/") if p]
            if len(parts) == 1:
                b.create_file(root, parts[0], data, mode=0o755)
            elif len(parts) == 2 and parts[0] == "bin":
                b.create_file(bin_ino, parts[1], data, mode=0o755)
            elif len(parts) == 2 and parts[0] == "etc" and parts[1] != "motd":
                b.create_file(etc, parts[1], data)
            elif len(parts) == 2 and parts[0] == "dev":
                b.create_file(dev, parts[1], data)
            elif len(parts) == 2 and parts[0] == "proc":
                b.create_file(proc, parts[1], data)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b.finalize())
    return path


def virtio_disk_args(disk_path: Union[str, Path]) -> List[str]:
    """QEMU args attaching a raw disk as legacy virtio-blk-pci."""
    p = Path(disk_path)
    return [
        "-drive",
        f"id=pyoshd,file={p},if=none,format=raw",
        "-device",
        "virtio-blk-pci,drive=pyoshd,disable-modern=on",
    ]


def virtio_net_args(hostfwd: Optional[str] = None) -> List[str]:
    """QEMU user-net + legacy virtio-net-pci (matches virtio_net.c I/O BAR driver)."""
    netdev = "user,id=net0"
    if hostfwd:
        netdev = f"user,id=net0,hostfwd={hostfwd}"
    return [
        "-netdev",
        netdev,
        "-device",
        "virtio-net-pci,netdev=net0,disable-modern=on",
    ]


if __name__ == "__main__":
    out = Path("build/rootfs.img")
    create_rootfs(out)
    print(f"wrote {out} ({out.stat().st_size} bytes)")
