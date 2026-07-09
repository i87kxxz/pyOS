"""Final edge cases: interrupts off, long wrap, print without clear, iso build."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pyos import Kernel, Screen
from pyos.toolchain import Toolchain

OUT = Path(__file__).resolve().parent


def run_qemu(image: Path, seconds: float = 2.0) -> str:
    tools = Toolchain()
    serial_log = OUT / f"_edge_{image.stem}.log"
    if serial_log.exists():
        serial_log.unlink()
    proc = subprocess.Popen(
        [
            tools.qemu,
            "-fda",
            str(image),
            "-display",
            "none",
            "-serial",
            f"file:{serial_log}",
            "-no-reboot",
            "-no-shutdown",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(seconds)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
    return serial_log.read_text(encoding="utf-8", errors="replace") if serial_log.exists() else ""


def main():
    findings = []

    # interrupts disabled — no keyboard, no syscall init?
    k = Kernel(arch="x86", enable_interrupts=False)

    @k.on_boot
    def m():
        Screen.clear()
        Screen.print("noirq", row=0)

    @k.on_keypress
    def on_key(key=None):
        pass

    img = OUT / "noirq.bin"
    k.build(str(img))
    glue = k.compile()
    serial = run_qemu(img, 2.0)
    (OUT / "noirq_serial.txt").write_text(serial, encoding="utf-8")
    findings.append(
        {
            "name": "enable_interrupts=False",
            "glue_flag": "enable_interrupts = PYOS_FALSE" in glue,
            "serial": serial,
            "detail": "kmain skips idt/pic/syscall/sti when False — keypress handler flag still set but IRQ never delivered",
            "status": "works-as-coded",
        }
    )

    # long string starting at row 24 — wraps/truncates without panic
    k2 = Kernel(arch="x86")

    @k2.on_boot
    def long():
        Screen.clear()
        Screen.print("X" * 200, row=24, col=0)

    img2 = OUT / "longwrap.bin"
    k2.build(str(img2))
    serial2 = run_qemu(img2, 2.0)
    findings.append(
        {
            "name": "long print at row=24 wraps/truncates",
            "panicked": "PANIC" in serial2,
            "status": "edge",
            "detail": "screen_print_at starts valid then silently stops when r>=HEIGHT — no panic for overflow length",
            "boot_ok": "Boot complete" in serial2,
        }
    )

    # format=iso
    k3 = Kernel(arch="x86")

    @k3.on_boot
    def iso():
        Screen.print("iso")

    try:
        out = k3.build(str(OUT / "test.iso"), format="iso")
        size = Path(out).stat().st_size
        findings.append({"name": "build format=iso", "status": "works", "path": out, "size": size})
    except Exception as e:
        findings.append({"name": "build format=iso", "status": "bug", "error": str(e)})

    # Python Screen.set_cursor clamps; C panics — inconsistency
    findings.append(
        {
            "name": "set_cursor clamp vs panic mismatch",
            "status": "bug",
            "detail": (
                "Python Screen.set_cursor clamps to 0..24/0..79. "
                "C screen_set_cursor panics on OOB. "
                "Build-time never emits invalid cursor from Python clamp, "
                "but docs imply same behavior."
            ),
        }
    )

    # print() always advances row even when using col-only intent
    findings.append(
        {
            "name": "Screen.print always newline semantics",
            "status": "misleading",
            "detail": (
                "After every Screen.print, Python cursor_row+=1 and col=0. "
                "Cannot print two strings on same line via successive print() without print_at/col. "
                "Also print with only col= set still forces next line."
            ),
        }
    )

    path = OUT / "edge_probe_report.json"
    path.write_text(json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(findings, indent=2, ensure_ascii=False))
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
