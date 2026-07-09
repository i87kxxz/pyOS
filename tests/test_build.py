"""pyOS build and codegen tests."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pyos import Kernel, Screen
from pyos.toolchain import Toolchain


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
    assert "KernelConfig" in glue
    assert "PYOS_TRUE" in glue or "PYOS_FALSE" in glue


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
    text = symbols.read_text(encoding="utf-8")
    assert "boot" in text
    assert "main" in text


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
