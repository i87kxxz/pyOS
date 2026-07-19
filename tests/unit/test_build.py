"""pyOS unit tests — codegen honesty + Multiboot build signature."""

from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pyos import Kernel, Screen, Memory, CapabilityError, UnsupportedOpError
from pyos.api.syscalls import SysCall
from pyos.build.toolchain import Toolchain


def test_toolchain_has_gcc_m32():
    tools = Toolchain()
    statuses = {s.name: s for s in tools.status()}
    assert "gcc (-m32)" in statuses
    assert statuses["gcc (-m32)"].ok, statuses["gcc (-m32)"].detail


def test_codegen_emits_c_glue():
    kernel = Kernel(arch="x86")

    @kernel.on_boot
    def main():
        Screen.clear()
        Screen.print("hi", row=1, col=0, color="green")

    glue = kernel.compile()
    assert "screen_clear" in glue
    assert "screen_print_at" in glue
    assert "pyos_user_boot" in glue
    assert "stack_size" in glue
    assert "has_timer_handler" in glue


def test_stack_size_emitted():
    kernel = Kernel(arch="x86", stack_size=32768)
    glue = kernel.compile()
    assert "32768" in glue


def test_invalid_color_raises():
    kernel = Kernel(arch="x86")

    @kernel.on_boot
    def main():
        Screen.set_color("not_a_color")

    try:
        kernel.compile()
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_utf8_print_raises():
    kernel = Kernel(arch="x86")

    @kernel.on_boot
    def main():
        Screen.print("عربي")

    try:
        kernel.compile()
        assert False, "expected UnsupportedOpError"
    except UnsupportedOpError:
        pass


def test_malloc_symbol_in_glue():
    kernel = Kernel(arch="x86")

    @kernel.on_boot
    def main():
        Screen.clear()
        p = Memory.malloc(64)
        Memory.free(p)

    glue = kernel.compile()
    assert "heap_malloc(64u)" in glue
    assert "heap_free(" in glue


def test_on_interrupt_rejected():
    kernel = Kernel(arch="x86")
    try:

        @kernel.on_interrupt(33)
        def h():
            pass

        assert False
    except UnsupportedOpError:
        pass


def test_filesystem_capability():
    kernel = Kernel(arch="x86")
    try:
        kernel.seed_file("x.txt", "hi")
        assert False
    except CapabilityError:
        pass

    k2 = Kernel(arch="x86", enable_filesystem=True)
    k2.seed_file("motd.txt", "hello\n")
    glue = k2.compile()
    assert "vfs_create" in glue
    assert "motd.txt" in glue


def test_syscall_codegen_six_args():
    """DSL syscalls must call the 6-arg Linux i386-style dispatch signature."""
    kernel = Kernel(arch="x86")

    @kernel.on_boot
    def main():
        Screen.clear()
        SysCall.exit(0)
        SysCall.sleep(10)
        SysCall.get_time()
        SysCall.call(4, 1, 0, 5)

    glue = kernel.compile()
    assert "syscall_dispatch(SYS_EXIT, 0, 0, 0, 0, 0, 0)" in glue
    assert "syscall_dispatch(SYS_SLEEP, 10, 0, 0, 0, 0, 0)" in glue
    assert "syscall_dispatch(SYS_TIME, 0, 0, 0, 0, 0, 0)" in glue
    assert "syscall_dispatch(4, 1, 0, 5, 0, 0, 0)" in glue


def test_syscall_isr_stores_return_in_saved_eax():
    """Assembly stub must overwrite pusha-saved EAX so popa does not discard the result."""
    isr = (ROOT / "pyos" / "kernel" / "arch" / "x86" / "isr.S").read_text(encoding="utf-8")
    assert "movl %eax, 28(%esp)" in isr
    assert "call S(syscall_handler_c)" in isr
    # Six args pushed (ebp,edi,esi,edx,ecx,ebx,eax) → 28-byte cleanup
    assert "addl $28, %esp" in isr


def test_build_multiboot_elf(tmp_path):
    kernel = Kernel(arch="x86")

    @kernel.on_boot
    def main():
        Screen.clear()
        Screen.print("test")

    out = tmp_path / "testos.bin"
    kernel.build(str(out), format="bin")
    data = out.read_bytes()
    assert data[:4] == b"\x7fELF"
    # Multiboot magic 0x1BADB002 must be in the first 8 KiB
    magic = struct.pack("<I", 0x1BADB002)
    assert magic in data[:8192]
    symbols = Path(str(out) + ".symbols.json")
    assert symbols.exists()
    meta = symbols.read_text(encoding="utf-8")
    assert "multiboot-elf" in meta
    # Must not be constrained to the old 64-sector floppy payload window
    assert len(data) > 512


def test_build_allows_kernel_larger_than_floppy_limit(tmp_path):
    """Gate: boot image path is not capped at 64 * 512 bytes."""
    from pyos.build.builder import MAX_KERNEL_BYTES, OSBuilder

    assert MAX_KERNEL_BYTES > 64 * 512
    assert not hasattr(OSBuilder, "KERNEL_SECTORS") or OSBuilder.__dict__.get("KERNEL_SECTORS") is None


def test_priority_order_in_glue():
    kernel = Kernel(arch="x86")

    @kernel.on_boot(priority=1)
    def late():
        Screen.print("late", row=1)

    @kernel.on_boot(priority=0)
    def early():
        Screen.print("early", row=0)

    glue = kernel.compile()
    assert glue.index("boot_early") < glue.index("boot_late")


def test_x86_64_rejected():
    try:
        Kernel(arch="x86_64")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "x86" in str(e)


def test_human_debug_translate():
    from pyos.debug import translate_serial_line

    line = translate_serial_line("Heap exhausted: asked 4096")
    assert "Increase Kernel" in line or "heap_size" in line


def test_full_os_flags_build(tmp_path):
    kernel = Kernel(
        arch="x86",
        enable_paging=True,
        enable_user_mode=True,
        enable_processes=True,
        enable_filesystem=True,
        heap_size=2 * 1024 * 1024,
    )

    @kernel.on_boot
    def main():
        Screen.clear()
        Screen.print("full", row=0)

    @kernel.on_keypress
    def on_key(key=None):
        pass

    @kernel.on_timer(interval_ms=500)
    def tick():
        pass

    kernel.seed_file("motd.txt", "Welcome\n")
    out = tmp_path / "full.bin"
    kernel.build(str(out))
    assert out.exists()
    assert out.read_bytes()[:4] == b"\x7fELF"
    glue = kernel.compile()
    assert "enable_paging = PYOS_TRUE" in glue
    assert "enable_processes = PYOS_TRUE" in glue
    assert "vfs_mount_root" in glue
    assert "task_start_init" in glue


def test_task_struct_has_context_fields():
    """Phase 1: Task must hold pid/state/esp/eip/eflags/cr3/kernel stack."""
    task_h = (ROOT / "pyos" / "kernel" / "include" / "task.h").read_text(encoding="utf-8")
    for field in ("pid", "state", "esp", "eip", "eflags", "cr3", "kstack"):
        assert field in task_h
    assert "task_switch_asm" in task_h
    switch = (ROOT / "pyos" / "kernel" / "arch" / "x86" / "switch.S").read_text(encoding="utf-8")
    assert "task_switch_asm" in switch
    assert "mov" in switch and "cr3" in switch


def test_paging_apis_present():
    paging_h = (ROOT / "pyos" / "kernel" / "include" / "paging.h").read_text(encoding="utf-8")
    for sym in (
        "paging_map_page",
        "paging_unmap_page",
        "paging_create_directory",
        "page_fault_handler",
        "paging_is_mapped",
    ):
        assert sym in paging_h
    pmm_h = (ROOT / "pyos" / "kernel" / "include" / "pmm.h").read_text(encoding="utf-8")
    assert "pmm_alloc_pages" in pmm_h
    assert "PMM_PAGE_SIZE" in pmm_h


def test_processes_codegen_flag():
    kernel = Kernel(arch="x86", enable_processes=True, enable_paging=True)
    glue = kernel.compile()
    assert "enable_processes = PYOS_TRUE" in glue
    assert "enable_paging = PYOS_TRUE" in glue
    assert "task_start_init" in glue


def test_linux_i386_syscall_numbers():
    """Phase 2: default ABI matches Linux i386 syscall_32.tbl."""
    from pyos.api.syscalls import SysCallNumber

    assert SysCallNumber.SYS_EXIT.value == 1
    assert SysCallNumber.SYS_FORK.value == 2
    assert SysCallNumber.SYS_READ.value == 3
    assert SysCallNumber.SYS_WRITE.value == 4
    assert SysCallNumber.SYS_OPEN.value == 5
    assert SysCallNumber.SYS_CLOSE.value == 6
    assert SysCallNumber.SYS_WAITPID.value == 7
    assert SysCallNumber.SYS_EXECVE.value == 11
    assert SysCallNumber.SYS_GETPID.value == 20
    assert SysCallNumber.SYS_BRK.value == 45
    assert SysCallNumber.SYS_IOCTL.value == 54
    assert SysCallNumber.SYS_MMAP2.value == 192
    assert SysCallNumber.SYS_MUNMAP.value == 91
    assert SysCallNumber.SYS_NANOSLEEP.value == 162
    assert SysCallNumber.SYS_SLEEP.value == 162
    assert SysCallNumber.SYS_TIME.value == 13
    assert SysCallNumber.SYS_SOCKETCALL.value == 102
    assert SysCallNumber.SYS_SELECT.value == 82
    assert SysCallNumber.SYS_POLL.value == 168

    hdr = (ROOT / "pyos" / "kernel" / "include" / "syscall.h").read_text(encoding="utf-8")
    assert "#define SYS_FORK            2" in hdr
    assert "#define SYS_EXECVE          11" in hdr
    assert "#define SYS_MMAP2           192" in hdr
    assert "#define SYS_SOCKETCALL      102" in hdr
    assert "#define SYS_SELECT          82" in hdr
    assert "#define SYS_POLL            168" in hdr
    assert "PYOS_SYS_MALLOC" in hdr


def test_network_codegen_flag():
    kernel = Kernel(arch="x86", enable_network=True)
    glue = kernel.compile()
    assert "enable_network = PYOS_TRUE" in glue
    assert "net_init();" in glue
    assert kernel.capabilities.get("network") is True


def test_ext2_alias_enables_filesystem():
    """enable_ext2 is an honest alias for the VFS/ext2 mount path."""
    k = Kernel(arch="x86", enable_ext2=True)
    assert k.config.enable_filesystem is True
    assert k.config.enable_ext2 is True
    assert k.capabilities["filesystem"] is True
    assert k.capabilities["ext2"] is True
    assert k.capabilities["virtio_blk"] is True
    glue = k.compile()
    assert "enable_filesystem = PYOS_TRUE" in glue
    assert "vfs_mount_root" in glue
    assert "filesystem/ext2" in glue or "virtio-blk" in glue


def test_linux_abi_default_and_reject_false():
    k = Kernel(arch="x86")
    assert k.config.enable_linux_abi is True
    assert k.capabilities["linux_abi"] is True
    info = k.get_info()
    assert info["linux_abi"] is True

    try:
        Kernel(arch="x86", enable_linux_abi=False)
        assert False, "expected UnsupportedOpError"
    except UnsupportedOpError as e:
        assert "linux_abi" in str(e).lower() or "Linux i386" in str(e)


def test_rootfs_path_metadata_in_glue():
    k = Kernel(
        arch="x86",
        enable_filesystem=True,
        rootfs_path="build/rootfs.img",
    )
    assert k.config.rootfs_path == "build/rootfs.img"
    assert k.get_info()["rootfs_path"] == "build/rootfs.img"
    glue = k.compile()
    assert "build/rootfs.img" in glue
    assert "--disk" in glue


def test_linux_userland_codegen_bundle():
    """Phase 6: full Linux-ABI flag set emits mount + init + comments."""
    k = Kernel(
        arch="x86",
        enable_paging=True,
        enable_user_mode=True,
        enable_processes=True,
        enable_filesystem=True,
        enable_network=True,
        enable_linux_abi=True,
        rootfs_path="rootfs.img",
    )
    assert k.capabilities["linux_abi"] is True
    assert k.capabilities["virtio_net"] is True
    glue = k.compile()
    assert "enable_paging = PYOS_TRUE" in glue
    assert "enable_user_mode = PYOS_TRUE" in glue
    assert "enable_processes = PYOS_TRUE" in glue
    assert "enable_filesystem = PYOS_TRUE" in glue
    assert "enable_network = PYOS_TRUE" in glue
    assert "vfs_mount_root" in glue
    assert "net_init();" in glue
    assert "task_start_init" in glue
    assert "userland boot" in glue or "Linux i386" in glue


def test_virtio_net_args():
    from pyos.build.rootfs import virtio_net_args

    args = virtio_net_args()
    assert "-netdev" in args
    assert any("user,id=net0" in a for a in args)
    assert any("virtio-net-pci" in a and "disable-modern=on" in a for a in args)


def test_socket_constants_in_headers():
    sock_h = (ROOT / "pyos" / "kernel" / "include" / "socket.h").read_text(encoding="utf-8")
    assert "SOCKOP_SOCKET" in sock_h
    assert "SOCKOP_CONNECT" in sock_h
    assert "SOCKOP_SETSOCKOPT" in sock_h
    assert "AF_INET" in sock_h
    net_h = (ROOT / "pyos" / "kernel" / "include" / "net.h").read_text(encoding="utf-8")
    assert "net_ping" in net_h
    assert "net_init" in net_h
    pci_h = (ROOT / "pyos" / "kernel" / "include" / "pci.h").read_text(encoding="utf-8")
    assert "PCI_DEVICE_VIRTIO_NET" in pci_h


def test_elf_hi_image_parses():
    """Tiny write+exit ELF is a valid ELF32 i386 ET_EXEC."""
    from pyos.user.tiny_elf import build_hi_elf, elf_entry

    elf = build_hi_elf()
    assert elf[:4] == b"\x7fELF"
    assert elf[4] == 1  # class 32
    assert elf[5] == 1  # LSB
    e_type = struct.unpack_from("<H", elf, 16)[0]
    e_machine = struct.unpack_from("<H", elf, 18)[0]
    assert e_type == 2
    assert e_machine == 3
    entry = elf_entry(elf)
    assert entry == 0x08048054
    # Embedded message
    assert b"hi\n" in elf


def test_elf_c_loader_symbols_present():
    elf_h = (ROOT / "pyos" / "kernel" / "include" / "elf.h").read_text(encoding="utf-8")
    assert "elf_load(" in elf_h
    assert "Elf32Ehdr" in elf_h
    assert "PT_LOAD" in elf_h or "ELF_PT_LOAD" in elf_h
    task_h = (ROOT / "pyos" / "kernel" / "include" / "task.h").read_text(encoding="utf-8")
    assert "task_fork" in task_h
    assert "task_execve" in task_h
    assert "enter_userspace" in task_h


def test_kernel_cflags_disable_sse():
    """Freestanding builds must not emit SSE (invalid opcode under early QEMU)."""
    src = (ROOT / "pyos" / "build" / "builder.py").read_text(encoding="utf-8")
    assert '"-mno-sse"' in src
    assert '"-mno-sse2"' in src


def test_linux_abi_docs_and_examples_present():
    """Phase 6/7 gate: DSL docs + examples must exist and describe limits honestly."""
    abi = ROOT / "docs" / "LINUX_ABI.md"
    assert abi.is_file(), "docs/LINUX_ABI.md required"
    text = abi.read_text(encoding="utf-8")
    assert "Linux i386" in text
    assert "Non-goals" in text or "out of scope" in text.lower()
    assert "enable_linux_abi" in text
    assert "virtio" in text.lower()
    examples = ROOT / "examples" / "linux"
    assert examples.is_dir(), "examples/linux/ required"
    assert (examples / "README.md").is_file()
    assert (examples / "busybox_userland.py").is_file()
    example = (examples / "busybox_userland.py").read_text(encoding="utf-8")
    assert "enable_filesystem" in example or "enable_ext2" in example
    assert "enable_linux_abi" in example
    readme = (examples / "README.md").read_text(encoding="utf-8")
    assert "LINUX_ABI" in readme or "linux" in readme.lower()
