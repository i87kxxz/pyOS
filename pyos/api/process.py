"""Process API — available when Kernel capability 'processes' is enabled."""

from __future__ import annotations

from typing import Callable, List, Optional

from .errors import CapabilityError


class Process:
    """Declare user processes at build time (emitted when processes capability is on)."""

    _spawns: List[dict] = []
    _kernel_ref = None

    @classmethod
    def bind_kernel(cls, kernel) -> None:
        cls._kernel_ref = kernel

    @classmethod
    def _require(cls) -> None:
        k = cls._kernel_ref
        if k is None or not k.capabilities.get("processes"):
            raise CapabilityError(
                "processes",
                "Enable with Kernel(enable_processes=True) once Phase 4 runtime is linked",
            )

    @classmethod
    def spawn(cls, name: str, entry: Optional[Callable] = None) -> int:
        cls._require()
        pid = len(cls._spawns) + 1
        cls._spawns.append({"name": name, "entry": entry, "pid": pid})
        return pid

    @classmethod
    def _reset(cls) -> None:
        cls._spawns = []

    @classmethod
    def _get_spawns(cls) -> List[dict]:
        return list(cls._spawns)
