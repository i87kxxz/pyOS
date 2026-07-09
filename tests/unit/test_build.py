"""pyOS unit tests — codegen honesty + build signature."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pyos import Kernel, Screen, Memory, CapabilityError, UnsupportedOpError
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


def test_build_bin_boot_signature(tmp_path):
    kernel = Kernel(arch="x86")

    @kernel.on_boot
    def main():
        Screen.clear()
        Screen.print("test")

    out = tmp_path / "testos.bin"
    kernel.build(str(out), format="bin")
    data = out.read_bytes()
    assert len(data) >= 512
    assert data[510:512] == b"\x55\xaa"
    symbols = Path(str(out) + ".symbols.json")
    assert symbols.exists()


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
    glue = kernel.compile()
    assert "enable_paging = PYOS_TRUE" in glue
    assert "enable_processes = PYOS_TRUE" in glue
    assert "vfs_mount_root" in glue
    assert "task_start_init" in glue
