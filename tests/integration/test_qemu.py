"""QEMU integration smoke tests."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pyos import Kernel, Screen
from pyos.build.toolchain import Toolchain
from pyos.emulator import QEMURunner


def _read_log(log: Path) -> str:
    return log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""


def _run_serial(
    image: Path,
    seconds: float = 2.0,
    disk: Path | None = None,
    network: bool = False,
    until: str | tuple[str, ...] | None = None,
) -> str:
    """Run QEMU until *seconds* elapse, or earlier if all *until* needles appear."""
    tools = Toolchain()
    log = image.with_suffix(".serial.log")
    if log.exists():
        log.unlink()
    boot = QEMURunner()._boot_args(str(image))
    cmd = [tools.qemu, *boot]
    if boot[:1] != ["-kernel"]:
        cmd.extend(["-boot", "order=a"])
    cmd.extend(
        [
            "-display",
            "none",
            "-serial",
            f"file:{log}",
            "-no-reboot",
            "-no-shutdown",
        ]
    )
    if disk is not None:
        cmd.extend(QEMURunner.disk_args(str(disk)))
    if network:
        cmd.extend(QEMURunner.net_args(True))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    needles: tuple[str, ...] = ()
    if until is not None:
        needles = (until,) if isinstance(until, str) else tuple(until)
    text = ""
    deadline = time.time() + seconds
    try:
        while time.time() < deadline:
            time.sleep(0.25)
            text = _read_log(log)
            if needles and all(n in text for n in needles):
                # Brief grace for trailing lines after the match.
                time.sleep(0.4)
                text = _read_log(log)
                break
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    # Give Windows a moment to flush serial file
    time.sleep(0.3)
    return _read_log(log)


@pytest.mark.skipif(not Toolchain().qemu, reason="QEMU not installed (qemu-system-i386)")
def test_qemu_boot_ok(tmp_path):
    k = Kernel(arch="x86")

    @k.on_boot
    def main():
        Screen.clear()
        Screen.print("OK", row=0)

    img = tmp_path / "ok.bin"
    k.build(str(img))
    assert img.read_bytes()[:4] == b"\x7fELF"
    serial = _run_serial(img, seconds=6.0, until="Boot complete")
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


def test_emulator_prefers_kernel_for_elf(tmp_path):
    img = tmp_path / "fake.elf"
    img.write_bytes(b"\x7fELF" + b"\0" * 60)
    args = QEMURunner()._boot_args(str(img))
    assert args == ["-kernel", str(img)]


@pytest.mark.skipif(not Toolchain().qemu, reason="QEMU not installed (qemu-system-i386)")
def test_qemu_two_tasks_alternate(tmp_path):
    """Phase 1 gate: enable_processes runs two demo tasks that print to serial."""
    k = Kernel(arch="x86", enable_paging=True, enable_processes=True)

    @k.on_boot
    def main():
        Screen.clear()
        Screen.print("procs", row=0)

    img = tmp_path / "procs.bin"
    k.build(str(img))
    serial = _run_serial(
        img,
        seconds=8.0,
        until=("Boot complete", "taskA", "taskB", "PAGE FAULT"),
    )
    assert "Boot complete" in serial
    assert "PANIC" not in serial
    assert "taskA" in serial, serial[-800:]
    assert "taskB" in serial, serial[-800:]
    # Alternation: both markers appear more than once
    assert serial.count("taskA") >= 2
    assert serial.count("taskB") >= 2
    # Page fault from faultor demo: logged and killed (no infinite loop / survive)
    assert "PAGE FAULT" in serial
    assert "faultor" in serial
    assert "faultor-survived" not in serial
    # Tasks keep running after the faulting task is killed
    fa = serial.find("PAGE FAULT")
    assert serial.find("taskA", fa) != -1 or serial.find("taskB", fa) != -1


@pytest.mark.skipif(not Toolchain().qemu, reason="QEMU not installed (qemu-system-i386)")
def test_qemu_elf_write_exit(tmp_path):
    """Phase 2 gate: seed tiny ELF, execve it, see write+exit on serial."""
    from pyos.user.tiny_elf import build_hi_elf

    k = Kernel(
        arch="x86",
        enable_paging=True,
        enable_user_mode=True,
        enable_processes=True,
        enable_filesystem=True,
        heap_size=2 * 1024 * 1024,
    )
    k.seed_file("hi", build_hi_elf())

    @k.on_boot
    def main():
        Screen.clear()
        Screen.print("elf", row=0)

    img = tmp_path / "elfhi.bin"
    k.build(str(img))
    serial = _run_serial(
        img,
        seconds=8.0,
        until=("Boot complete", "hi", "task exit"),
    )
    assert "Boot complete" in serial, serial[-800:]
    assert "PANIC" not in serial
    assert "init ELF scheduled" in serial or "enter userspace ELF" in serial, serial[-800:]
    assert "hi" in serial, serial[-800:]
    assert "task exit" in serial, serial[-800:]


@pytest.mark.skipif(not Toolchain().qemu, reason="QEMU not installed (qemu-system-i386)")
def test_qemu_fork_exec_elf(tmp_path):
    """Phase 2/5 gate: fork + execve(child) from a tiny parent ELF seeded as init."""
    from pyos.user.tiny_elf import build_fork_exec_elf, build_hi_elf

    k = Kernel(
        arch="x86",
        enable_paging=True,
        enable_user_mode=True,
        enable_processes=True,
        enable_filesystem=True,
        heap_size=2 * 1024 * 1024,
    )
    # Without a disk, init execs seed "hi". Parent forks and execve("child").
    k.seed_file("child", build_hi_elf())
    k.seed_file("hi", build_fork_exec_elf(child_path="child"))

    @k.on_boot
    def main():
        Screen.clear()
        Screen.print("fork", row=0)

    img = tmp_path / "forkexec.bin"
    k.build(str(img))
    serial = _run_serial(
        img,
        seconds=10.0,
        until=("Boot complete", "hi", "fork-exec-ok"),
    )
    assert "Boot complete" in serial, serial[-1200:]
    assert "PANIC" not in serial, serial[-1200:]
    assert "init ELF scheduled" in serial or "enter userspace ELF" in serial, serial[-1200:]
    assert "hi" in serial, serial[-1200:]
    assert "fork-exec-ok" in serial, serial[-1200:]


@pytest.mark.skipif(not Toolchain().qemu, reason="QEMU not installed (qemu-system-i386)")
def test_qemu_ext2_motd_from_disk(tmp_path):
    """Phase 3 gate: virtio-blk + ext2 root, cat /etc/motd to serial."""
    from pyos.build.rootfs import create_rootfs

    disk = tmp_path / "rootfs.img"
    create_rootfs(disk, motd="Welcome to pyOS\n")

    k = Kernel(
        arch="x86",
        enable_paging=True,
        enable_filesystem=True,
        heap_size=2 * 1024 * 1024,
    )

    @k.on_boot
    def main():
        Screen.clear()
        Screen.print("disk", row=0)

    img = tmp_path / "disk.bin"
    k.build(str(img))
    serial = _run_serial(
        img,
        seconds=10.0,
        disk=disk,
        until=("Boot complete", "Welcome to pyOS"),
    )
    assert "Boot complete" in serial, serial[-1200:]
    assert "PANIC" not in serial
    assert "virtio-blk: ready" in serial or "ext2: mounted" in serial, serial[-1200:]
    assert "VFS root mounted (ext2)" in serial, serial[-1200:]
    assert "Welcome to pyOS" in serial, serial[-1200:]


@pytest.mark.skipif(not Toolchain().qemu, reason="QEMU not installed (qemu-system-i386)")
def test_qemu_virtio_net_ping_gateway(tmp_path):
    """Phase 4 gate: virtio-net + ICMP echo to QEMU user-net gateway 10.0.2.2."""
    k = Kernel(
        arch="x86",
        enable_network=True,
        heap_size=2 * 1024 * 1024,
    )

    @k.on_boot
    def main():
        Screen.clear()
        Screen.print("net", row=0)

    img = tmp_path / "net.bin"
    k.build(str(img))
    serial = _run_serial(
        img,
        seconds=12.0,
        network=True,
        until=("Boot complete", "net: ping 10.0.2.2 ok"),
    )
    assert "Boot complete" in serial, serial[-1500:]
    assert "PANIC" not in serial
    assert "virtio-net: ready" in serial, serial[-1500:]
    assert "net: ping 10.0.2.2 ok" in serial, serial[-1500:]


@pytest.mark.skipif(not Toolchain().qemu, reason="QEMU not installed (qemu-system-i386)")
def test_qemu_userland_shell(tmp_path):
    """Phase 5 gate: BusyBox rootfs + ash /init — echo/uname/ls on serial."""
    from pyos.build.rootfs import create_rootfs, find_busybox, ensure_ash_binary

    ash = ensure_ash_binary()
    assert ash is not None and ash.is_file(), "ash ELF must build (scripts/build_ash.py)"
    disk = tmp_path / "rootfs.img"
    create_rootfs(disk, motd="Welcome to pyOS userland\n", include_userland=True)
    assert find_busybox() is not None or (disk.read_bytes().find(b"busybox") >= 0)

    k = Kernel(
        arch="x86",
        enable_paging=True,
        enable_user_mode=True,
        enable_processes=True,
        enable_filesystem=True,
        heap_size=4 * 1024 * 1024,
    )

    @k.on_boot
    def main():
        Screen.clear()
        Screen.print("userland", row=0)

    img = tmp_path / "userland.bin"
    k.build(str(img))
    serial = _run_serial(
        img,
        seconds=16.0,
        disk=disk,
        until=("Boot complete", "hello from pyOS", "fork-parent-ok"),
    )
    assert "Boot complete" in serial, serial[-2000:]
    assert "PANIC" not in serial
    assert "ext2: mounted" in serial or "VFS root mounted (ext2)" in serial, serial[-2000:]
    assert "init ELF scheduled" in serial or "enter userspace ELF" in serial, serial[-2000:]
    # Shell banner / prompt
    assert "BusyBox" in serial or "# " in serial, serial[-2000:]
    # Demo builtins
    assert "hello from pyOS" in serial, serial[-2000:]
    assert "pyOS" in serial, serial[-2000:]  # uname sysname
    assert "i386" in serial, serial[-2000:]
    # fork + waitpid from ash demo (BusyBox applet fork+exec is best-effort; see LINUX_ABI.md)
    assert "fork failed" not in serial, serial[-2000:]
    assert "fork-child-ok" in serial, serial[-2000:]
    assert "fork-parent-ok" in serial, serial[-2000:]


def test_rootfs_includes_busybox_when_present(tmp_path):
    from pyos.build.rootfs import create_rootfs, find_busybox

    if find_busybox() is None:
        pytest.skip("BusyBox binary not in third_party/")
    disk = tmp_path / "rootfs.img"
    create_rootfs(disk, include_userland=True)
    data = disk.read_bytes()
    assert data[:4] != b"\x7fELF"  # disk image, not ELF
    # BusyBox payload embedded somewhere in the image
    assert b"\x7fELF" in data
