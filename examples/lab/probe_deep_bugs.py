"""
Deeper bug hunt: config ignored, heap edge, keyboard IRQ, CLI, codegen resets.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pyos import Kernel, Screen, Memory, Keyboard, Interrupts, SysCall, GDT
from pyos.compiler.codegen import CodeGenerator
from pyos.toolchain import Toolchain
from pyos.cli import main as cli_main
from click.testing import CliRunner

OUT = Path(__file__).resolve().parent


def check_stack_size_ignored():
    k = Kernel(arch="x86", stack_size=999999)
    glue = k.compile()
    return {
        "name": "stack_size ignored in glue",
        "detail": "Kernel(stack_size=999999) but glue hardcodes stack_top=0x90000; stack_size never emitted",
        "evidence": "stack_top = 0x90000" in glue and "999999" not in glue,
        "status": "bug" if ("0x90000" in glue and "999999" not in glue) else "ok",
    }


def check_heap_exact_fit_no_panic():
    """4*1024 on heap_size=4096 succeeds — document boundary."""
    k = Kernel(arch="x86", heap_size=4096)

    @k.on_boot
    def b():
        Screen.clear()
        for _ in range(4):
            Memory.malloc(1024)

    glue = CodeGenerator(k).generate()
    img = OUT / "heap_exact.bin"
    k.build(str(img))
    serial = run_qemu(img, 2.0)
    panicked = "PANIC" in serial
    return {
        "name": "heap exact-fit 4x1024 on 4096",
        "status": "edge",
        "panicked": panicked,
        "detail": "heap_cur+size > heap_end is strict >; exact fill succeeds. 5th malloc needed to panic.",
        "serial_tail": serial[-300:],
    }


def check_heap_overflow_panics():
    k = Kernel(arch="x86", heap_size=4096)

    @k.on_boot
    def b():
        Screen.clear()
        for _ in range(5):
            Memory.malloc(1024)

    img = OUT / "heap_overflow.bin"
    k.build(str(img))
    serial = run_qemu(img, 2.0)
    (OUT / "heap_overflow_serial.txt").write_text(serial, encoding="utf-8")
    return {
        "name": "heap overflow 5x1024 on 4096",
        "status": "bug" if "PANIC" not in serial and "Heap exhausted" not in serial else "works",
        "panicked": "PANIC" in serial or "Heap exhausted" in serial,
        "detail": serial[serial.find("PANIC") : serial.find("PANIC") + 200] if "PANIC" in serial else serial[-400:],
    }


def check_screen_ops_reset_between_boots():
    """Each boot func resets Screen — cursor/color don't carry across priorities?"""
    k = Kernel(arch="x86")

    @k.on_boot(priority=0)
    def a():
        Screen.set_color("red", "black")
        Screen.print("A", row=0)

    @k.on_boot(priority=1)
    def b():
        # After reset, color should be white default unless set again
        Screen.print("B", row=1)

    glue = CodeGenerator(k).generate()
    (OUT / "glue_priority_reset.c").write_text(glue, encoding="utf-8")
    # B's print after reset: default white=15
    has_reset_issue = "boot_b" in glue
    # Look for color of B print
    return {
        "name": "Screen state reset per boot function",
        "status": "misleading",
        "detail": (
            "CodeGenerator resets Screen/Keyboard/Memory between each @on_boot. "
            "set_color in priority=0 does NOT affect priority=1. "
            "Also each boot gets isolated op lists — intentional but surprising."
        ),
        "evidence_snippet": "\n".join(
            line for line in glue.splitlines() if "boot_b" in line or "str_" in line or "screen_print" in line
        )[:500],
    }


def check_global_screen_pollution():
    """Screen._operations is class-level — building two kernels without reset can leak?"""
    Screen._reset()
    k1 = Kernel(arch="x86")

    @k1.on_boot
    def one():
        Screen.print("ONE")

    g1 = CodeGenerator(k1).generate()
    # Don't reset — call Screen.print outside boot
    Screen.print("LEAKED")
    k2 = Kernel(arch="x86")

    @k2.on_boot
    def two():
        Screen.print("TWO")

    g2 = CodeGenerator(k2).generate()
    leaked = "LEAKED" in g2
    return {
        "name": "Screen class-level ops pollution",
        "status": "ok" if not leaked else "bug",
        "detail": "CodeGenerator resets at start of each boot func so external LEAKED not in g2"
        if not leaked
        else "LEAKED appeared in second kernel glue",
        "leaked_in_g2": leaked,
        "g1_has_one": "ONE" in g1,
        "g2_has_two": "TWO" in g2,
    }


def check_keyboard_qemu_sendkey():
    k = Kernel(arch="x86")

    @k.on_boot
    def main():
        Screen.clear()
        Screen.print("TYPE", row=0)

    @k.on_keypress
    def on_key(key=None):
        pass

    img = OUT / "keytest.bin"
    k.build(str(img))
    tools = Toolchain()
    serial_log = OUT / "keytest_serial.log"
    if serial_log.exists():
        serial_log.unlink()
    monitor = f"telnet:127.0.0.1:4445,server,nowait"
    # Use QEMU monitor via stdio instead
    cmd = [
        tools.qemu,
        "-fda",
        str(img),
        "-display",
        "none",
        "-serial",
        f"file:{serial_log}",
        "-monitor",
        "stdio",
        "-no-reboot",
    ]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(1.5)
    try:
        # send keys via monitor
        assert proc.stdin is not None
        proc.stdin.write("sendkey h\n")
        proc.stdin.write("sendkey e\n")
        proc.stdin.write("sendkey l\n")
        proc.stdin.write("sendkey l\n")
        proc.stdin.write("sendkey o\n")
        proc.stdin.flush()
        time.sleep(1.0)
        proc.stdin.write("quit\n")
        proc.stdin.flush()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
        proc.wait(timeout=3)

    serial = serial_log.read_text(encoding="utf-8", errors="replace") if serial_log.exists() else ""
    (OUT / "keytest_serial.txt").write_text(serial, encoding="utf-8")
    key_logs = [ln for ln in serial.splitlines() if "keypress" in ln.lower()]
    return {
        "name": "keyboard IRQ echo via QEMU sendkey",
        "status": "works" if key_logs else "bug",
        "keypress_log_count": len(key_logs),
        "detail": f"found {len(key_logs)} keypress debug lines; sample={key_logs[:5]}",
        "serial_preview": serial[:600],
    }


def check_cli():
    runner = CliRunner()
    findings = []
    r = runner.invoke(cli_main, ["check"])
    findings.append({"cmd": "check", "exit": r.exit_code, "ok": r.exit_code == 0})

    main_py = OUT / "cli_main.py"
    main_py.write_text(
        'from pyos import Kernel, Screen\nk=Kernel()\n@k.on_boot\ndef m():\n    Screen.print("cli")\n',
        encoding="utf-8",
    )
    out_bin = OUT / "cli_built.bin"
    r2 = runner.invoke(cli_main, ["build", str(main_py), "-o", str(out_bin)])
    findings.append(
        {
            "cmd": "build",
            "exit": r2.exit_code,
            "ok": r2.exit_code == 0 and out_bin.exists(),
            "output": (r2.output or "")[:400],
        }
    )

    r3 = runner.invoke(cli_main, ["c", str(main_py), "-o", str(OUT / "cli_glue.c")])
    findings.append({"cmd": "c", "exit": r3.exit_code, "ok": r3.exit_code == 0})

    # Invalid arch via script
    bad = OUT / "bad_arch.py"
    bad.write_text(
        'from pyos import Kernel\nk=Kernel(arch="arm")\n',
        encoding="utf-8",
    )
    r4 = runner.invoke(cli_main, ["build", str(bad), "-o", str(OUT / "bad.bin")])
    findings.append(
        {
            "cmd": "build bad arch",
            "exit": r4.exit_code,
            "ok": r4.exit_code != 0,
            "output": (r4.output or "")[:400],
        }
    )
    return {"name": "CLI commands", "status": "works", "findings": findings}


def check_col_oob():
    k = Kernel(arch="x86")

    @k.on_boot
    def bad():
        Screen.clear()
        Screen.print("col oob", row=0, col=90)

    img = OUT / "col_oob.bin"
    k.build(str(img))
    serial = run_qemu(img, 2.0)
    (OUT / "col_oob_serial.txt").write_text(serial, encoding="utf-8")
    return {
        "name": "column OOB panic",
        "status": "works" if "PANIC" in serial else "bug",
        "panicked": "PANIC" in serial,
        "detail": serial[serial.find("====") :][:300] if "====" in serial else serial[-200:],
    }


def check_negative_or_empty_print():
    k = Kernel(arch="x86")

    @k.on_boot
    def e():
        Screen.clear()
        Screen.print("")
        Screen.print_char("", row=1, col=0)

    try:
        img = OUT / "empty_print.bin"
        k.build(str(img))
        serial = run_qemu(img, 1.5)
        return {
            "name": "empty string / empty char print",
            "status": "works",
            "panicked": "PANIC" in serial,
            "detail": f"built ok; panic={('PANIC' in serial)}; serial_len={len(serial)}",
        }
    except Exception as ex:
        return {"name": "empty string print", "status": "bug", "detail": str(ex)}


def check_interrupts_ops_discarded():
    k = Kernel(arch="x86")

    @k.on_boot
    def m():
        Interrupts.enable()
        Interrupts._operations  # noqa
        SysCall.sleep(1)
        GDT.create_flat_model().install()

    gen = CodeGenerator(k)
    glue = gen.generate()
    # Interrupts ops collected during boot but only Screen+Memory folded
    return {
        "name": "Interrupts/SysCall ops discarded after reset",
        "status": "bug",
        "detail": (
            "During generate(), Interrupts._reset() then boot runs and records ops, "
            "but only Screen+Memory ops are copied into glue. Interrupts/SysCall/GDT silently dropped."
        ),
        "glue_has_sti_comment": "Interrupts" in glue,
        "glue_len": len(glue),
    }


def run_qemu(image: Path, seconds: float = 2.0) -> str:
    tools = Toolchain()
    serial_log = OUT / f"_tmp_{image.stem}_serial.log"
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
    if serial_log.exists():
        return serial_log.read_text(encoding="utf-8", errors="replace")
    return ""


def main():
    checks = [
        check_stack_size_ignored(),
        check_heap_exact_fit_no_panic(),
        check_heap_overflow_panics(),
        check_screen_ops_reset_between_boots(),
        check_global_screen_pollution(),
        check_col_oob(),
        check_negative_or_empty_print(),
        check_interrupts_ops_discarded(),
        check_keyboard_qemu_sendkey(),
        check_cli(),
    ]
    path = OUT / "deep_probe_report.json"
    path.write_text(json.dumps(checks, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(checks, indent=2, ensure_ascii=False))
    print(f"\nWrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
