"""QEMU integration smoke tests."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pyos import Kernel, Screen
from pyos.build.toolchain import Toolchain


def _run_serial(image: Path, seconds: float = 2.0) -> str:
    tools = Toolchain()
    log = image.with_suffix(".serial.log")
    if log.exists():
        log.unlink()
    # Use explicit raw floppy drive so BIOS LBA works reliably in QEMU
    drive = f"file={image},format=raw,if=floppy"
    proc = subprocess.Popen(
        [
            tools.qemu,
            "-drive",
            drive,
            "-display",
            "none",
            "-serial",
            f"file:{log}",
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
    # Give Windows a moment to flush serial file
    time.sleep(0.2)
    return log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""


def test_qemu_boot_ok(tmp_path):
    k = Kernel(arch="x86")

    @k.on_boot
    def main():
        Screen.clear()
        Screen.print("OK", row=0)

    img = tmp_path / "ok.bin"
    k.build(str(img))
    serial = _run_serial(img, seconds=4.0)
    assert "Boot complete" in serial
    assert "PANIC" not in serial


def test_qemu_oob_panics(tmp_path):
    k = Kernel(arch="x86")

    @k.on_boot
    def main():
        Screen.clear()
        Screen.print("x", row=30)

    # Build-time should reject OOB now
    try:
        k.compile()
        assert False, "expected ValueError for OOB row"
    except ValueError:
        pass
