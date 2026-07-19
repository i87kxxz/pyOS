"""
Human-readable debug helpers for pyOS build/runtime logs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Optional


PANIC_PATTERNS = [
    (
        re.compile(r"outside the VGA", re.I),
        "Screen position is invalid — use row 0..24 and col 0..79.",
    ),
    (
        re.compile(r"Heap exhausted", re.I),
        "Increase Kernel(heap_size=...) or allocate less memory.",
    ),
    (
        re.compile(r"no @kernel\.on_keypress", re.I),
        "Add @kernel.on_keypress handler if you want keyboard input.",
    ),
    (
        re.compile(r"General protection fault", re.I),
        "Likely bad pointer or invalid segment access in the kernel.",
    ),
    (
        re.compile(r"Page fault", re.I),
        "Kernel touched unmapped memory — check addresses and heap usage.",
    ),
]


def translate_serial_line(line: str) -> str:
    """Turn a raw serial line into a clearer message when possible."""
    raw = line.rstrip("\n")
    if not raw:
        return raw

    if raw.startswith("========== pyOS PANIC"):
        return raw
    if raw.startswith("Where :") or raw.startswith("Why   :") or raw.startswith("Hint  :"):
        return raw
    if raw.startswith("Detail: EIP="):
        return raw + "  (technical detail — read Where/Why/Hint above first)"

    for pattern, advice in PANIC_PATTERNS:
        if pattern.search(raw):
            return f"{raw}\n  → {advice}"
    return raw


def format_serial_log(lines: Iterable[str]) -> str:
    return "\n".join(translate_serial_line(line) for line in lines)


def load_symbol_hints(image_path: str) -> List[str]:
    path = Path(image_path)
    symbols = path.with_suffix(path.suffix + ".symbols.json")
    if not symbols.exists():
        return []
    try:
        import json

        data = json.loads(symbols.read_text(encoding="utf-8"))
        hints = []
        for sym in data.get("symbols", []):
            kind = sym.get("kind", "?")
            name = sym.get("name", "?")
            hints.append(f"  - {kind}: {name}")
        return hints
    except Exception:
        return []


def explain_build_error(message: str) -> str:
    text = message
    lower = message.lower()
    if "not found" in lower and "gcc" in lower:
        text += "\n  → Install MinGW-w64: winget install -e --id BrechtSanders.WinLibs.POSIX.UCRT"
    if "nasm" in lower and ("not found" in lower or "failed" in lower):
        text += "\n  → Install NASM: winget install -e --id NASM.NASM"
    if "undefined reference" in lower:
        text += "\n  → A C symbol is missing — runtime/glue mismatch; run pyos check and rebuild."
    if "too large" in lower:
        text += "\n  → Kernel image exceeded MAX_KERNEL_BYTES; reduce glue/seeds or raise the limit in builder.py."
    if "multiboot" in lower:
        text += "\n  → Multiboot header missing — check start.S .multiboot section and linker.ld."
    return text
