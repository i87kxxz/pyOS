"""
pyOS Command Line Interface
"""

from __future__ import annotations

import click
import sys
import subprocess
from pathlib import Path
from typing import Optional

from .debug import explain_build_error, format_serial_log, load_symbol_hints


@click.group()
@click.version_option(version="1.0.1", prog_name="pyOS")
def main():
    """
    pyOS - Build real operating systems with a Python DSL.

    Your Python records intent; pyOS builds a freestanding C+ASM kernel.
    """
    pass


def _load_kernel_from_source(source: str):
    source_path = Path(source)
    code = source_path.read_text(encoding="utf-8")
    namespace = {"__name__": "__pyos_build__", "__file__": str(source_path)}
    exec(compile(code, str(source_path), "exec"), namespace)
    for obj in namespace.values():
        if hasattr(obj, "build") and hasattr(obj, "_boot_functions"):
            return obj
    return None


@main.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("-o", "--output", default="os.bin", help="Output file path")
@click.option(
    "-f",
    "--format",
    "fmt",
    type=click.Choice(["iso", "bin"]),
    default="bin",
    help="Output format (bin recommended)",
)
@click.option("-a", "--arch", type=click.Choice(["x86"]), default="x86", help="Target architecture")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
def build(source: str, output: str, fmt: str, arch: str, verbose: bool):
    """Build OS from Python source file."""
    click.echo(f"Building {source} -> {output}")
    try:
        if verbose:
            click.echo(f"  Architecture: {arch}")
            click.echo(f"  Format: {fmt}")
        kernel = _load_kernel_from_source(source)
        if kernel is None:
            click.echo(
                "Error: No Kernel object found in source file\n"
                "  Hint: create kernel = Kernel(arch='x86') and use @kernel.on_boot",
                err=True,
            )
            sys.exit(1)
        result = kernel.build(output, format=fmt)
        click.echo(f"Built successfully: {result}")
    except Exception as e:
        click.echo(explain_build_error(f"Error: {e}"), err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@main.command()
@click.argument("image", type=click.Path(exists=True))
@click.option("-m", "--memory", default=128, help="Memory in MB")
@click.option("--gdb", "gdb_mode", is_flag=True, help="Pause and wait for GDB on :1234")
@click.option("--disk", default=None, type=click.Path(exists=True), help="ext2 rootfs disk image (virtio-blk)")
@click.option("--net/--no-net", default=False, help="Attach virtio-net (user networking)")
@click.option("--headless", is_flag=True, help="Run without opening a QEMU window")
@click.option("--timeout", default=0, show_default=True, help="Stop after N seconds (0 = wait until closed)")
def run(image: str, memory: int, gdb_mode: bool, disk: Optional[str], net: bool, headless: bool, timeout: int):
    """Run OS image in QEMU."""
    from .emulator import QEMURunner, QEMUError

    click.echo(f"Running {image} in QEMU...")
    if disk:
        click.echo(f"  Disk: {disk} (virtio-blk)")
    if net:
        click.echo("  Net: virtio-net-pci (user)")
    try:
        runner = QEMURunner()
        process = runner.run(
            image, memory=memory, debug=gdb_mode, serial_stdio=headless, disk=disk, network=net
        )
        click.echo("QEMU started. Close the window to exit." if not headless else "QEMU started in headless mode.")
        if timeout > 0:
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.terminate()
        else:
            process.wait()
    except QEMUError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("image", type=click.Path(exists=True))
@click.option("-m", "--memory", default=128, help="Memory in MB")
@click.option("--gdb", "gdb_mode", is_flag=True, help="Also enable GDB stub")
@click.option("--timeout", default=8, help="Seconds to capture serial log (headless)")
@click.option("--disk", default=None, type=click.Path(exists=True), help="ext2 rootfs disk image")
def debug(image: str, memory: int, gdb_mode: bool, timeout: int, disk: Optional[str]):
    """
    Human-readable debug: run with serial log and explain panics.

    Example:
        pyos debug myos.bin
    """
    from .emulator import QEMURunner, QEMUError
    from .build.toolchain import Toolchain

    tools = Toolchain()
    if not tools.qemu:
        click.echo("Error: QEMU not found. Run: pyos check", err=True)
        sys.exit(1)

    click.echo(f"Debug run: {image}")
    hints = load_symbol_hints(image)
    if hints:
        click.echo("Python handlers in this image:")
        for h in hints:
            click.echo(h)
        click.echo("")

    boot_args = QEMURunner()._boot_args(image)
    cmd = [tools.qemu, *boot_args]
    if boot_args[:1] != ["-kernel"]:
        cmd.extend(["-boot", "order=a"])
    cmd.extend(
        [
            "-m",
            str(memory),
            "-serial",
            "stdio",
            "-display",
            "none",
            "-no-reboot",
            "-no-shutdown",
        ]
    )
    cmd.extend(QEMURunner.disk_args(disk))
    if gdb_mode:
        cmd.extend(["-s", "-S"])
        click.echo("GDB stub on localhost:1234 (CPU paused)")

    click.echo("Serial log (translated):")
    click.echo("-" * 40)
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            out, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, _ = proc.communicate()
        lines = (out or "").splitlines()
        click.echo(format_serial_log(lines) if lines else "(no serial output captured)")
        click.echo("-" * 40)
        click.echo(
            "Tip: panics show Where / Why / Hint first; EIP hex is only secondary detail."
        )
    except QEMUError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(explain_build_error(f"Error: {e}"), err=True)
        sys.exit(1)


@main.command("mkrootfs")
@click.option("-o", "--output", default="rootfs.img", help="Output disk image path")
@click.option("--motd", default="Welcome to pyOS\n", help="Contents of /etc/motd")
def mkrootfs(output: str, motd: str):
    """Create an ext2 rootfs image (/etc/motd, /bin/busybox, /init)."""
    from .build.rootfs import create_rootfs

    path = create_rootfs(output, motd=motd)
    click.echo(f"Created {path} ({path.stat().st_size} bytes)")
    click.echo(f"  Contains /init (ash), /bin/busybox when third_party binary present")
    click.echo(f"  Run with: pyos run myos.bin --disk {path}")


@main.command("c")
@click.argument("source", type=click.Path(exists=True))
@click.option("-o", "--output", default="glue.c", help="Output C glue path")
def emit_c(source: str, output: str):
    """Generate C glue from Python source (for inspection)."""
    click.echo(f"Generating C glue: {source} -> {output}")
    try:
        kernel = _load_kernel_from_source(source)
        if kernel is None:
            click.echo("Error: No Kernel object found", err=True)
            sys.exit(1)
        code = kernel.compile()
        Path(output).write_text(code, encoding="utf-8")
        click.echo(f"Wrote {output}")
    except Exception as e:
        click.echo(explain_build_error(f"Error: {e}"), err=True)
        sys.exit(1)


@main.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("-o", "--output", default="glue.c", help="Output file path")
def asm(source: str, output: str):
    """Deprecated alias: emits C glue (runtime is C, bootloader is ASM)."""
    emit_c.callback(source, output)


@main.command()
def check():
    """Check if required tools are installed (GCC -m32, NASM, QEMU)."""
    from .build.toolchain import Toolchain

    click.echo("Checking required tools...")
    click.echo("")
    tools = Toolchain()
    ok_all = True
    for status in tools.status():
        if status.ok:
            click.echo(f"[OK] {status.name}: {status.version or 'found'}")
            if status.path:
                click.echo(f"     {status.path}")
        else:
            ok_all = False
            click.echo(f"[MISSING] {status.name}")
            if status.detail:
                for line in status.detail.splitlines():
                    click.echo(f"  {line}")
    click.echo("")
    if ok_all:
        click.echo("All tools ready. Build with: pyos build main.py -o myos.bin")
    else:
        click.echo("Fix missing tools, then re-run: pyos check")
        sys.exit(1)


@main.command()
@click.argument("name", default="myos")
def new(name: str):
    """Create a new pyOS project."""
    project_dir = Path(name)
    if project_dir.exists():
        click.echo(f"Error: Directory '{name}' already exists", err=True)
        sys.exit(1)
    project_dir.mkdir()
    (project_dir / "main.py").write_text(
        '''"""My Operating System built with pyOS"""

from pyos import Kernel, Screen

kernel = Kernel(arch="x86")

@kernel.on_boot
def main():
    Screen.clear()
    Screen.set_color("green", "black")
    Screen.print("Welcome to My OS!")
    Screen.print("Built with pyOS", row=2)
    Screen.set_color("yellow", "black")
    Screen.print("Type keys — they echo if you add @kernel.on_keypress", row=4)

@kernel.on_keypress
def on_key(key=None):
    """Runtime keyboard handler (echo is built into the C runtime)."""
    pass

if __name__ == "__main__":
    kernel.build("myos.bin")
''',
        encoding="utf-8",
    )
    (project_dir / "README.md").write_text(
        f"""# {name}

Built with pyOS (Python API → C runtime + ASM bootloader).

## Build

```bash
pyos build main.py -o {name}.bin
```

## Run

```bash
pyos run {name}.bin
```

## Debug (human-readable serial log)

```bash
pyos debug {name}.bin
```
""",
        encoding="utf-8",
    )
    click.echo(f"Created project: {name}/")
    click.echo(f"  cd {name}")
    click.echo(f"  pyos build main.py -o {name}.bin")
    click.echo(f"  pyos run {name}.bin")


if __name__ == "__main__":
    main()
