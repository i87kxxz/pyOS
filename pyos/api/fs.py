"""Filesystem API — available when Kernel capability 'filesystem' is enabled."""

from __future__ import annotations

from typing import Dict, List, Union

from .errors import CapabilityError


class File:
    """Seed files into the OS image at build time; runtime uses syscalls."""

    _seed_files: Dict[str, bytes] = {}
    _kernel_ref = None

    @classmethod
    def bind_kernel(cls, kernel) -> None:
        cls._kernel_ref = kernel

    @classmethod
    def _require(cls) -> None:
        k = cls._kernel_ref
        if k is None or not k.capabilities.get("filesystem"):
            raise CapabilityError(
                "filesystem",
                "Enable with Kernel(enable_filesystem=True) or Kernel(enable_ext2=True)",
            )

    @classmethod
    def write_at_build(cls, path: str, data: Union[bytes, str]) -> None:
        cls._require()
        if isinstance(data, str):
            data = data.encode("ascii", errors="replace")
        cls._seed_files[path.lstrip("/")] = data

    @classmethod
    def _reset(cls) -> None:
        cls._seed_files = {}

    @classmethod
    def _get_seeds(cls) -> Dict[str, bytes]:
        return dict(cls._seed_files)

    @classmethod
    def list_seeds(cls) -> List[str]:
        return list(cls._seed_files.keys())
