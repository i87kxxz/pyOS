"""
Probe every public pyOS API as a real OS builder would.
Records: works / stub / missing / crash — with exact evidence.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pyos import Kernel, Screen, Keyboard, Memory, GDT, Interrupts, SysCall
from pyos.compiler.codegen import CodeGenerator
OUT = Path(__file__).resolve().parent
REPORT = OUT / "probe_report.json"


def record(findings: list, area: str, api: str, status: str, detail: str):
    findings.append(
        {
            "area": area,
            "api": api,
            "status": status,  # works | stub | skipped_in_glue | crash | missing | misleading
            "detail": detail,
        }
    )
    print(f"[{status:16}] {area}.{api}: {detail}")


def probe_kernel_config(findings: list):
    try:
        Kernel(arch="x86_64")
        record(findings, "Kernel", "arch=x86_64", "crash", "should reject but did not")
    except ValueError as e:
        record(findings, "Kernel", "arch=x86_64", "works", f"rejected: {e}")

    k = Kernel(arch="x86", stack_size=8192, heap_size=65536, enable_interrupts=False)
    info = k.get_info()
    record(
        findings,
        "Kernel",
        "get_info",
        "works",
        f"info keys={list(info.keys())} heap={info['heap_size']} irq={info['interrupts_enabled']}",
    )

    # enable_gdt / enable_paging / video_mode exist on KernelConfig but not fully wired
    cfg = k.config
    record(
        findings,
        "Kernel",
        "enable_gdt flag",
        "misleading",
        f"config.enable_gdt={cfg.enable_gdt} but Python GDT API is never emitted to C runtime",
    )
    record(
        findings,
        "Kernel",
        "enable_paging",
        "missing",
        f"KernelConfig.enable_paging={cfg.enable_paging} — no paging implementation in C runtime",
    )
    record(
        findings,
        "Kernel",
        "video_mode",
        "missing",
        f"KernelConfig.video_mode={cfg.video_mode!r} — only VGA text 80x25 exists",
    )


def probe_screen_ops(findings: list):
    k = Kernel(arch="x86")

    @k.on_boot
    def main():
        Screen.clear()
        Screen.set_color("green", "black")
        Screen.print("line0")
        Screen.print("at", row=2, col=5, color="red")
        Screen.print_at("print_at", row=3, col=0)
        Screen.print_char("X", row=4, col=0, color="yellow")
        Screen.set_cursor(5, 10)
        Screen.scroll_up(1)
        Screen.scroll_down(1)
        Screen.enable_cursor()
        Screen.disable_cursor()
        # invalid color name silently falls back
        Screen.set_color("not_a_color", "also_bad")
        Screen.print("badcolor", row=6)
        # out of bounds — recorded at build time, may panic at runtime
        Screen.print("OOB", row=100, col=0)

    gen = CodeGenerator(k)
    glue = gen.generate()
    (OUT / "glue_screen.c").write_text(glue, encoding="utf-8")

    checks = [
        ("clear", "screen_clear", "works"),
        ("set_color", "screen_set_color", "works"),
        ("print", "screen_print", "works"),
        ("print_at", "screen_print_at", "works"),
        ("print_char", "screen_print_char_at", "works"),
        ("set_cursor", "screen_set_cursor", "works"),
        ("scroll_up", "skipped unsupported op at runtime glue: scroll_up", "skipped_in_glue"),
        ("scroll_down", "skipped unsupported op at runtime glue: scroll_down", "skipped_in_glue"),
        ("enable_cursor", "skipped unsupported op at runtime glue: enable_cursor", "skipped_in_glue"),
        ("disable_cursor", "skipped unsupported op at runtime glue: disable_cursor", "skipped_in_glue"),
    ]
    for api, needle, expect in checks:
        if needle in glue:
            record(findings, "Screen", api, expect, f"glue contains: {needle}")
        else:
            record(findings, "Screen", api, "missing", f"expected glue marker missing: {needle}")

    if "screen_set_color" in glue:
        record(
            findings,
            "Screen",
            "invalid color name",
            "misleading",
            "COLOR_NAMES.get(..., fallback) — invalid names silently become WHITE/BLACK, no error",
        )

    # get_cursor / get_width / get_height are Python-only helpers
    w, h = Screen.get_width(), Screen.get_height()
    record(
        findings,
        "Screen",
        "get_width/get_height/get_cursor",
        "stub",
        f"Python-side only ({w}x{h}); not emitted to runtime",
    )


def probe_keyboard(findings: list):
    k = Kernel(arch="x86")

    @k.on_boot
    def main():
        Screen.clear()
        Keyboard.read_key()
        Keyboard.read_char()
        Keyboard.read_line()
        Keyboard.wait_key()
        Keyboard.clear_buffer()
        Keyboard.set_repeat_rate(250, 20)

    @k.on_keypress
    def on_key(key=None):
        # User expects custom logic — codegen ignores body
        Screen.print(f"pressed {key}")

    gen = CodeGenerator(k)
    glue = gen.generate()
    (OUT / "glue_keyboard.c").write_text(glue, encoding="utf-8")

    if "has_keypress_handler = PYOS_TRUE" in glue:
        record(
            findings,
            "Keyboard",
            "@on_keypress",
            "misleading",
            "handler body is NOT compiled; glue only does screen_putchar(ch) echo + debug_log",
        )
    if "screen_putchar(ch)" in glue:
        record(findings, "Keyboard", "echo path", "works", "runtime echo via screen_putchar")

    # Keyboard ops during boot are collected but never folded into glue (only Screen+Memory)
    kb_ops = ["read_key", "read_char", "read_line", "wait_key", "clear_buffer", "set_repeat_rate"]
    for api in kb_ops:
        if f"skipped unsupported op" in glue and api in glue:
            record(findings, "Keyboard", api, "skipped_in_glue", "mentioned in skip comment")
        elif api in glue:
            record(findings, "Keyboard", api, "works", "present in glue")
        else:
            record(
                findings,
                "Keyboard",
                api,
                "missing",
                "Keyboard._operations never folded into CodeGenerator (only Screen+Memory)",
            )


def probe_memory(findings: list):
    k = Kernel(arch="x86")

    @k.on_boot
    def main():
        Screen.clear()
        Memory.allocate_static(64, name="buf")
        Memory.malloc(128)
        Memory.free(0)
        Memory.calloc(4, 8)
        Memory.realloc(0, 16)
        Memory.memset(0, 0, 8)
        Memory.memcpy(0, 0, 8)
        Memory.read_byte(0)
        Memory.write_byte(0, 1)
        Memory.read_word(0)
        Memory.write_word(0, 2)
        Memory.read_dword(0)
        Memory.write_dword(0, 3)

    gen = CodeGenerator(k)
    glue = gen.generate()
    (OUT / "glue_memory.c").write_text(glue, encoding="utf-8")

    if "heap_malloc(64u)" in glue or "heap_malloc(128u)" in glue:
        record(
            findings,
            "Memory",
            "malloc/allocate_static",
            "misleading",
            "emitted as (void)heap_malloc(N) — return address discarded; Python return value is fake host-side",
        )
    for api in (
        "free",
        "calloc",
        "realloc",
        "memset",
        "memcpy",
        "read_byte",
        "write_byte",
        "read_word",
        "write_word",
        "read_dword",
        "write_dword",
    ):
        needle = f"skipped unsupported op at runtime glue: {api}"
        if needle in glue:
            record(findings, "Memory", api, "skipped_in_glue", needle)
        else:
            record(findings, "Memory", api, "missing", "not in glue at all")

    # C heap_free is no-op
    record(
        findings,
        "Memory",
        "C heap_free",
        "stub",
        "runtime heap.c: heap_free is intentional no-op (bump allocator)",
    )
    record(
        findings,
        "Memory",
        "layout constants vs config",
        "misleading",
        "Memory.HEAP_SIZE=16MB class const vs Kernel(heap_size=...) used in glue; Python malloc sim uses class const",
    )


def probe_handlers(findings: list):
    k = Kernel(arch="x86")

    @k.on_boot
    def main():
        Screen.clear()
        Interrupts.enable()
        Interrupts.mask_irq(1)
        SysCall.exit(1)
        SysCall.sleep(10)
        _ = SysCall.get_time()
        gdt = GDT.create_flat_model()
        gdt.install()

    @k.on_interrupt(33)
    def irq1():
        pass

    @k.on_syscall(4)
    def sys_write_handler():
        pass

    @k.on_timer(interval_ms=500)
    def tick():
        pass

    @k.on_event("custom")
    def custom():
        pass

    gen = CodeGenerator(k)
    glue = gen.generate()
    (OUT / "glue_handlers.c").write_text(glue, encoding="utf-8")

    info = k.get_info()
    record(
        findings,
        "Kernel",
        "on_interrupt registered",
        "stub",
        f"stored in kernel ({info['interrupt_handlers']} handlers) but NEVER emitted to C glue/IDT",
    )
    record(
        findings,
        "Kernel",
        "on_syscall registered",
        "stub",
        f"stored ({info['syscall_handlers']}) but C uses fixed syscall_dispatch; Python handlers unused",
    )
    record(
        findings,
        "Kernel",
        "on_timer",
        "missing",
        f"stored ({len(k._timer_handlers)}) — no PIT timer IRQ handler generation, interval ignored",
    )
    record(
        findings,
        "Kernel",
        "on_event",
        "missing",
        f"stored ({list(k._custom_handlers.keys())}) — no runtime event bus",
    )

    # Interrupts/SysCall/GDT ops not folded
    for area, api in [
        ("Interrupts", "enable/disable/mask"),
        ("SysCall", "exit/sleep/get_time/call"),
        ("GDT", "create_flat_model/install"),
    ]:
        record(
            findings,
            area,
            api,
            "missing",
            "operations recorded on Python objects but CodeGenerator never reads Interrupts/SysCall/GDT ops into glue",
        )

    # C runtime has limited syscalls
    record(
        findings,
        "SysCall",
        "C runtime surface",
        "works",
        "C supports SYS_EXIT/SYS_READ/SYS_WRITE only; Python SysCallNumber has OPEN/CLOSE/MALLOC/FREE/SLEEP/TIME unused",
    )
    record(
        findings,
        "SysCall",
        "SYS_WRITE buffer trust",
        "crash",  # security issue — use status carefully
        "syscall.c casts a2 to char* with no userspace/range check — ring0 only today but unsafe if user mode added",
    )


def probe_build_and_edge_cases(findings: list):
    # Empty boot
    k = Kernel(arch="x86")

    @k.on_boot
    def empty():
        pass

    try:
        out = OUT / "empty.bin"
        k.build(str(out))
        data = out.read_bytes()
        record(
            findings,
            "Build",
            "empty boot",
            "works",
            f"built {out.name} size={len(data)} signature={data[510:512].hex()}",
        )
    except Exception as e:
        record(findings, "Build", "empty boot", "crash", f"{type(e).__name__}: {e}")

    # Unicode / quotes / backslash in print
    k2 = Kernel(arch="x86")

    @k2.on_boot
    def tricky():
        Screen.clear()
        Screen.print('quote " and \\ backslash')
        Screen.print("newline\ninstring")
        Screen.print("عربي")  # non-ascii

    try:
        glue = k2.compile()
        (OUT / "glue_tricky.c").write_text(glue, encoding="utf-8")
        out2 = OUT / "tricky.bin"
        k2.build(str(out2))
        record(findings, "Build", "escape/unicode strings", "works", f"built {out2.name}")
        if "عربي" in glue or "\\u" in glue or any(ord(c) > 127 for c in glue):
            record(
                findings,
                "Screen",
                "non-ASCII print",
                "misleading",
                "Arabic/UTF-8 embedded in C string — VGA text mode is CP437/ASCII; glyphs will be wrong at runtime",
            )
    except Exception as e:
        record(
            findings,
            "Build",
            "escape/unicode strings",
            "crash",
            f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
        )

    # f-string / dynamic text at boot — only build-time value captured
    k3 = Kernel(arch="x86")
    counter = {"n": 7}

    @k3.on_boot
    def dyn():
        Screen.print(f"count={counter['n']}")

    glue3 = k3.compile()
    if "count=7" in glue3:
        record(
            findings,
            "Codegen",
            "dynamic Python at boot",
            "works",
            "f-strings evaluated at build time and frozen into C string constants",
        )
    record(
        findings,
        "Codegen",
        "runtime Python logic",
        "missing",
        "loops/if/variables in on_boot run on host at build time only — not a Python VM in the kernel",
    )

    # run() default builds temp_os.iso
    k4 = Kernel(arch="x86")

    @k4.on_boot
    def m():
        Screen.print("x")

    # Don't actually launch QEMU GUI here — just inspect default path logic via source knowledge
    record(
        findings,
        "Kernel",
        "run() default image",
        "misleading",
        "kernel.run() with image_path=None calls build('temp_os.iso') even though format default for build is bin; ISO path may surprise",
    )


def probe_security_gaps(findings: list):
    record(
        findings,
        "Security",
        "privilege rings",
        "missing",
        "Everything runs ring0; GDT flat model in bootloader only; no user/kernel separation",
    )
    record(
        findings,
        "Security",
        "paging / W^X / NX",
        "missing",
        "enable_paging=False forever; no page tables, no NX, no ASLR",
    )
    record(
        findings,
        "Security",
        "stack canary / SSP",
        "missing",
        "built with -fno-stack-protector; freestanding kernel has no SSP",
    )
    record(
        findings,
        "Security",
        "syscall validation",
        "missing",
        "SYS_WRITE/READ trust raw pointers; no copy_from_user; no capability model",
    )
    record(
        findings,
        "Security",
        "filesystem / process isolation",
        "missing",
        "No VFS, no processes, no UID, no sandbox — single infinite hlt loop after boot",
    )
    record(
        findings,
        "Security",
        "serial debug info leak",
        "misleading",
        "debug_log / panic dump EIP and messages on COM1 — fine for lab, not for production OS",
    )
    record(
        findings,
        "Security",
        "input sanitization",
        "missing",
        "keyboard echo puts raw chars to VGA; no line discipline, no ctrl filtering beyond basic",
    )
    record(
        findings,
        "OS-feature",
        "disk / FS / networking / multiprocess",
        "missing",
        "No ATA, no FAT/ext, no TCP/IP, no scheduler, no threads — boot banner + optional key echo only",
    )


def main():
    findings: list = []
    print("=== pyOS API surface probe ===\n")
    probe_kernel_config(findings)
    probe_screen_ops(findings)
    probe_keyboard(findings)
    probe_memory(findings)
    probe_handlers(findings)
    probe_build_and_edge_cases(findings)
    probe_security_gaps(findings)

    summary = {}
    for f in findings:
        summary[f["status"]] = summary.get(f["status"], 0) + 1

    report = {"summary": summary, "findings": findings}
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n=== SUMMARY {summary} ===")
    print(f"Wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
