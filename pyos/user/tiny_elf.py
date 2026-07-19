"""Build minimal i386 Linux ELFs for pyOS userland smoke tests."""

from __future__ import annotations

import struct


def _pack_elf32(code: bytes, data: bytes = b"", load_base: int = 0x08048000) -> bytes:
    ehdr_size = 52
    phdr_size = 32
    phoff = ehdr_size
    text_off = ehdr_size + phdr_size  # 84
    file_size = text_off + len(code) + len(data)
    entry = load_base + text_off

    ehdr = bytearray(ehdr_size)
    ehdr[0:4] = b"\x7fELF"
    ehdr[4] = 1  # ELFCLASS32
    ehdr[5] = 1  # ELFDATA2LSB
    ehdr[6] = 1  # EV_CURRENT
    struct.pack_into("<HHI", ehdr, 16, 2, 3, 1)  # type, machine, version
    struct.pack_into("<III", ehdr, 24, entry, phoff, 0)  # entry, phoff, shoff
    struct.pack_into("<IHHHHHH", ehdr, 36, 0, ehdr_size, phdr_size, 1, 0, 0, 0)

    phdr = struct.pack(
        "<IIIIIIII",
        1,  # PT_LOAD
        0,
        load_base,
        load_base,
        file_size,
        file_size,
        7,
        0x1000,
    )
    return bytes(ehdr) + phdr + code + data


def build_hi_elf() -> bytes:
    """
    ET_EXEC ELF32 for EM_386.
    Loads at 0x08048000; entry runs write+exit syscalls.
    """
    load_base = 0x08048000
    text_off = 84

    code = bytearray()
    code += b"\xb8\x04\x00\x00\x00"  # mov eax, 4  (SYS_write)
    code += b"\xbb\x01\x00\x00\x00"  # mov ebx, 1  (stdout)
    imm_at = len(code) + 1
    code += b"\xb9\x00\x00\x00\x00"  # mov ecx, msg
    code += b"\xba\x03\x00\x00\x00"  # mov edx, 3
    code += b"\xcd\x80"  # int 0x80
    code += b"\xb8\x01\x00\x00\x00"  # mov eax, 1  (SYS_exit)
    code += b"\x31\xdb"  # xor ebx, ebx
    code += b"\xcd\x80"  # int 0x80
    msg = b"hi\n"
    msg_va = load_base + text_off + len(code)
    struct.pack_into("<I", code, imm_at, msg_va)
    return _pack_elf32(bytes(code), msg, load_base)


def build_fork_exec_elf(child_path: str = "hi") -> bytes:
    """
    fork(); child execve(child_path); parent waitpid + write \"fork-exec-ok\\n\".

    Path must be a seeded VFS file (default ``hi`` from build_hi_elf).
    """
    load_base = 0x08048000
    text_off = 84
    path = child_path.encode("ascii") + b"\0"
    marker = b"fork-exec-ok\n"

    code = bytearray()
    # fork
    code += b"\xb8\x02\x00\x00\x00"  # mov eax, 2
    code += b"\xcd\x80"  # int 0x80
    code += b"\x85\xc0"  # test eax, eax
    jz_at = len(code) + 1
    code += b"\x74\x00"  # jz child (rel8 patched)

    # parent: waitpid(pid, &status, 0)
    code += b"\x89\xc3"  # mov ebx, eax  (pid)
    status_imm_at = len(code) + 1
    code += b"\xb9\x00\x00\x00\x00"  # mov ecx, &status
    code += b"\x31\xd2"  # xor edx, edx
    code += b"\xb8\x07\x00\x00\x00"  # mov eax, 7  (waitpid)
    code += b"\xcd\x80"  # int 0x80
    # write(1, marker, len)
    code += b"\xb8\x04\x00\x00\x00"  # mov eax, 4
    code += b"\xbb\x01\x00\x00\x00"  # mov ebx, 1
    marker_imm_at = len(code) + 1
    code += b"\xb9\x00\x00\x00\x00"  # mov ecx, marker
    code += b"\xba" + bytes([len(marker)]) + b"\x00\x00\x00"  # mov edx, len
    code += b"\xcd\x80"  # int 0x80
    # exit(0)
    code += b"\xb8\x01\x00\x00\x00"
    code += b"\x31\xdb"
    code += b"\xcd\x80"

    child_off = len(code)
    rel = child_off - (jz_at + 1)
    assert -128 <= rel <= 127
    code[jz_at] = rel & 0xFF

    # child: execve(path, NULL, NULL)
    path_imm_at = len(code) + 1
    code += b"\xbb\x00\x00\x00\x00"  # mov ebx, path
    code += b"\x31\xc9"  # xor ecx, ecx
    code += b"\x31\xd2"  # xor edx, edx
    code += b"\xb8\x0b\x00\x00\x00"  # mov eax, 11 (execve)
    code += b"\xcd\x80"  # int 0x80
    # exec failed
    code += b"\xb8\x01\x00\x00\x00"
    code += b"\xbb\x01\x00\x00\x00"
    code += b"\xcd\x80"

    data_off = text_off + len(code)
    path_va = load_base + data_off
    marker_va = path_va + len(path)
    status_va = marker_va + len(marker)
    pad = (4 - (status_va & 3)) & 3
    status_va += pad

    struct.pack_into("<I", code, status_imm_at, status_va)
    struct.pack_into("<I", code, marker_imm_at, marker_va)
    struct.pack_into("<I", code, path_imm_at, path_va)

    data = path + marker + (b"\0" * pad) + struct.pack("<I", 0)
    return _pack_elf32(bytes(code), data, load_base)


def elf_entry(elf: bytes) -> int:
    return struct.unpack_from("<I", elf, 24)[0]


if __name__ == "__main__":
    data = build_hi_elf()
    with open("hi.elf", "wb") as f:
        f.write(data)
    print(f"wrote hi.elf ({len(data)} bytes), entry=0x{elf_entry(data):08x}")
    fe = build_fork_exec_elf()
    with open("fork_exec.elf", "wb") as f:
        f.write(fe)
    print(f"wrote fork_exec.elf ({len(fe)} bytes)")
