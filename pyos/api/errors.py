"""Honest API errors for pyOS — no silent stubs."""


class CapabilityError(Exception):
    """Raised when a Python API feature is not available in the current kernel."""

    def __init__(self, capability: str, hint: str = ""):
        self.capability = capability
        msg = f"Capability '{capability}' is not available in this pyOS build."
        if hint:
            msg = f"{msg}\n  Hint: {hint}"
        super().__init__(msg)


class BuildTimeOnlyError(Exception):
    """Raised when runtime Python logic is expected but only build-time recording exists."""

    def __init__(self, api: str, hint: str = ""):
        msg = (
            f"'{api}' cannot run arbitrary Python inside the C kernel. "
            "Only recorded build-time operations are emitted to C glue."
        )
        if hint:
            msg = f"{msg}\n  Hint: {hint}"
        super().__init__(msg)


class UnsupportedOpError(Exception):
    """Raised at codegen time when an operation cannot be emitted."""

    def __init__(self, op: str, hint: str = ""):
        msg = f"Unsupported kernel operation at build time: {op}"
        if hint:
            msg = f"{msg}\n  Hint: {hint}"
        super().__init__(msg)
