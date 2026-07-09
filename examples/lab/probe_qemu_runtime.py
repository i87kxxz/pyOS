"""
Build a stress OS, run under QEMU headless, capture serial, classify panics.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pyos import Kernel, Screen, Memory, Keyboard
from pyos.toolchain import Toolchain
from pyos.debug import translate_serial_line

OUT = Path(__file__).resolve().parent


def build_stress_os() -> Path:
    k = Kernel(arch="x86", heap_size=4096)  # tiny heap to force exhaustion later

    @k.on_boot
    def banner():
        Screen.clear()
        Screen.set_color("light_green", "black")
        Screen.print("pyOS STRESS LAB", row=0)
        Screen.print("serial=COM1 debug", row=1)
        # legitimate prints
        for i in range(3):
            Screen.print(f"line {i}", row=3 + i, color="white")
        # allocate until near limit (build-time emits multiple mallocs)
        Memory.malloc(1024)
        Memory.malloc(1024)
        Memory.malloc(1024)
        Memory.malloc(1024)  # should panic at runtime (heap 4096, aligned)

    @k.on_keypress
    def on_key(key=None):
        pass

    path = OUT / "stress.bin"
    k.build(str(path))
    glue = k.compile()
    (OUT / "glue_stress.c").write_text(glue, encoding="utf-8")
    return path


def build_oob_os() -> Path:
    k = Kernel(arch="x86")

    @k.on_boot
    def bad():
        Screen.clear()
        Screen.print("about to OOB", row=0)
        Screen.print("boom", row=30, col=0)  # row>24

    path = OUT / "oob.bin"
    k.build(str(path))
    return path


def build_ok_os() -> Path:
    k = Kernel(arch="x86")

    @k.on_boot
    def ok():
        Screen.clear()
        Screen.set_color("cyan", "black")
        Screen.print("OK BOOT", row=0)
        Screen.print("waiting keys...", row=2)

    @k.on_keypress
    def on_key(key=None):
        pass

    path = OUT / "ok.bin"
    k.build(str(path))
    return path


def run_qemu_serial(image: Path, seconds: float = 2.5) -> str:
    tools = Toolchain()
    qemu = tools.qemu
    if not qemu:
        raise RuntimeError("qemu not found")

    serial_log = OUT / f"{image.stem}_serial.log"
    if serial_log.exists():
        serial_log.unlink()

    cmd = [
        qemu,
        "-fda",
        str(image),
        "-display",
        "none",
        "-serial",
        f"file:{serial_log}",
        "-no-reboot",
        "-no-shutdown",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
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

    if serial_log.exists():
        raw = serial_log.read_bytes()
        # QEMU serial file may be binary-ish; decode loosely
        text = raw.decode("utf-8", errors="replace")
        return text
    return ""


def main():
    results = []
    print("=== Build + QEMU serial probes ===\n")

    for name, builder, expect_panic in [
        ("ok", build_ok_os, False),
        ("oob", build_oob_os, True),
        ("stress_heap", build_stress_os, True),
    ]:
        print(f"-- {name}")
        try:
            img = builder()
            serial = run_qemu_serial(img)
            (OUT / f"{name}_serial.txt").write_text(serial, encoding="utf-8", errors="replace")
            translated = "\n".join(
                translate_serial_line(line) for line in serial.splitlines() if line.strip()
            )
            (OUT / f"{name}_serial_human.txt").write_text(translated, encoding="utf-8")
            has_panic = "PANIC" in serial or "panic" in serial.lower() or "==========" in serial
            results.append(
                {
                    "case": name,
                    "image": str(img),
                    "expect_panic": expect_panic,
                    "saw_panic": has_panic,
                    "serial_preview": serial[:800],
                    "ok": (has_panic == expect_panic) if expect_panic else (not has_panic and len(serial) > 0),
                }
            )
            print(f"   panic={has_panic} expect={expect_panic} serial_len={len(serial)}")
            if serial.strip():
                print("   first lines:", repr(serial.splitlines()[:5]))
        except Exception as e:
            results.append({"case": name, "error": f"{type(e).__name__}: {e}", "ok": False})
            print(f"   ERROR: {e}")

    report = {"results": results}
    path = OUT / "qemu_probe_report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {path}")
    failed = [r for r in results if not r.get("ok")]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
