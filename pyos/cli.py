"""
pyOS Command Line Interface
"""

import click
import sys
from pathlib import Path


@click.group()
@click.version_option(version="0.1.0", prog_name="pyOS")
def main():
    """
    pyOS - Build Operating Systems with Python
    
    Write your OS in Python, compile to Assembly and Machine Code.
    """
    pass


@main.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("-o", "--output", default="os.iso", help="Output file path")
@click.option("-f", "--format", "fmt", type=click.Choice(["iso", "bin"]), default="iso", help="Output format")
@click.option("-a", "--arch", type=click.Choice(["x86", "x86_64"]), default="x86", help="Target architecture")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
def build(source: str, output: str, fmt: str, arch: str, verbose: bool):
    """
    Build OS from Python source file.
    
    Example:
        pyos build main.py -o myos.iso
    """
    click.echo(f"Building {source} -> {output}")
    
    try:
        # Import and execute the source file
        source_path = Path(source)
        
        if verbose:
            click.echo(f"  Architecture: {arch}")
            click.echo(f"  Format: {fmt}")
        
        # Read and execute the Python file
        code = source_path.read_text()
        
        # Create a namespace for execution
        namespace = {}
        exec(code, namespace)
        
        # Find the kernel object
        kernel = None
        for name, obj in namespace.items():
            if hasattr(obj, 'build') and hasattr(obj, '_boot_functions'):
                kernel = obj
                break
        
        if kernel is None:
            click.echo("Error: No Kernel object found in source file", err=True)
            sys.exit(1)
        
        # Build
        result = kernel.build(output, format=fmt)
        
        click.echo(f"✓ Built successfully: {result}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@main.command()
@click.argument("image", type=click.Path(exists=True))
@click.option("-m", "--memory", default=128, help="Memory in MB")
@click.option("-d", "--debug", is_flag=True, help="Enable debug mode (GDB)")
def run(image: str, memory: int, debug: bool):
    """
    Run OS image in QEMU.
    
    Example:
        pyos run myos.iso
        pyos run myos.bin --debug
    """
    from .emulator import QEMURunner, QEMUError
    
    click.echo(f"Running {image} in QEMU...")
    
    if debug:
        click.echo("Debug mode enabled. Connect GDB to localhost:1234")
    
    try:
        runner = QEMURunner()
        process = runner.run(image, memory=memory, debug=debug)
        
        click.echo("QEMU started. Close the window to exit.")
        process.wait()
        
    except QEMUError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("image", type=click.Path(exists=True))
@click.option("-m", "--memory", default=128, help="Memory in MB")
def debug(image: str, memory: int):
    """
    Run OS in debug mode with GDB server.
    
    Example:
        pyos debug myos.iso
    
    Then connect with: gdb -ex "target remote localhost:1234"
    """
    from .emulator import QEMURunner, QEMUError
    
    click.echo(f"Starting {image} in debug mode...")
    click.echo("GDB server listening on localhost:1234")
    click.echo("Connect with: gdb -ex 'target remote localhost:1234'")
    click.echo("")
    
    try:
        runner = QEMURunner()
        process = runner.run(image, memory=memory, debug=True)
        process.wait()
        
    except QEMUError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("-o", "--output", default="output.asm", help="Output file path")
def asm(source: str, output: str):
    """
    Generate Assembly code from Python source.
    
    Example:
        pyos asm main.py -o kernel.asm
    """
    click.echo(f"Generating Assembly: {source} -> {output}")
    
    try:
        source_path = Path(source)
        code = source_path.read_text()
        
        namespace = {}
        exec(code, namespace)
        
        kernel = None
        for name, obj in namespace.items():
            if hasattr(obj, 'compile') and hasattr(obj, '_boot_functions'):
                kernel = obj
                break
        
        if kernel is None:
            click.echo("Error: No Kernel object found", err=True)
            sys.exit(1)
        
        asm_code = kernel.compile()
        
        with open(output, "w") as f:
            f.write(asm_code)
        
        click.echo(f"✓ Assembly generated: {output}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
def check():
    """
    Check if required tools are installed.
    
    Example:
        pyos check
    """
    from .compiler.assembler import Assembler
    from .emulator import QEMURunner
    
    click.echo("Checking required tools...")
    click.echo("")
    
    # Check NASM
    if Assembler.is_nasm_available():
        version = Assembler.get_nasm_version()
        click.echo(f"✓ NASM: {version}")
    else:
        click.echo("✗ NASM: Not found")
        click.echo("  Install: https://www.nasm.us/")
    
    # Check QEMU
    if QEMURunner.is_available():
        version = QEMURunner.get_version()
        click.echo(f"✓ QEMU: {version}")
    else:
        click.echo("✗ QEMU: Not found")
        click.echo("  Install: https://www.qemu.org/download/")
    
    click.echo("")


@main.command()
@click.argument("name", default="myos")
def new(name: str):
    """
    Create a new pyOS project.
    
    Example:
        pyos new myos
    """
    project_dir = Path(name)
    
    if project_dir.exists():
        click.echo(f"Error: Directory '{name}' already exists", err=True)
        sys.exit(1)
    
    project_dir.mkdir()
    
    # Create main.py
    main_py = project_dir / "main.py"
    main_py.write_text('''"""
My Operating System built with pyOS
"""

from pyos import Kernel, Screen

# Create kernel
kernel = Kernel(arch="x86")

@kernel.on_boot
def main():
    """Main boot function."""
    Screen.clear()
    Screen.set_color("green", "black")
    Screen.print("Welcome to My OS!")
    Screen.print("Built with pyOS", row=2)
    Screen.set_color("white", "black")
    Screen.print("Press any key...", row=4)

# Build the OS
if __name__ == "__main__":
    kernel.build("myos.iso")
''')
    
    # Create README
    readme = project_dir / "README.md"
    readme.write_text(f'''# {name}

An operating system built with pyOS.

## Build

```bash
pyos build main.py -o {name}.iso
```

## Run

```bash
pyos run {name}.iso
```

## Debug

```bash
pyos debug {name}.iso
```
''')
    
    click.echo(f"✓ Created new pyOS project: {name}/")
    click.echo("")
    click.echo("Next steps:")
    click.echo(f"  cd {name}")
    click.echo(f"  pyos build main.py -o {name}.iso")
    click.echo(f"  pyos run {name}.iso")


if __name__ == "__main__":
    main()
