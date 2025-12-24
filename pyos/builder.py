"""
pyOS Builder - Build OS images
"""

import subprocess
import tempfile
import shutil
import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .kernel import Kernel


class BuildError(Exception):
    """Raised when build fails."""
    pass


class OSBuilder:
    """
    Builds complete OS images from compiled kernel.
    """
    
    def __init__(self, kernel: 'Kernel'):
        self.kernel = kernel
        self.bootloader_path = Path(__file__).parent / "boot" / "bootloader.asm"
    
    def build_bin(self, output_path: str) -> str:
        """
        Build a raw binary image.
        
        Args:
            output_path: Output file path
        
        Returns:
            Path to the built image.
        """
        from .compiler.assembler import Assembler
        from .compiler.codegen import CodeGenerator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Assemble bootloader
            assembler = Assembler(self.kernel.config.arch.value)
            bootloader_bin = tmpdir / "bootloader.bin"
            
            bootloader_asm = self.bootloader_path.read_text()
            assembler.assemble_to_file(bootloader_asm, str(bootloader_bin), "bin")
            
            # Generate and assemble kernel
            generator = CodeGenerator(self.kernel)
            kernel_asm = generator.generate()
            
            kernel_bin = tmpdir / "kernel.bin"
            assembler.assemble_to_file(kernel_asm, str(kernel_bin), "bin")
            
            # Combine bootloader + kernel
            with open(output_path, "wb") as out:
                # Write bootloader (512 bytes)
                bootloader_data = bootloader_bin.read_bytes()
                out.write(bootloader_data)
                
                # Write kernel
                kernel_data = kernel_bin.read_bytes()
                out.write(kernel_data)
                
                # Pad to 16 sectors (8KB) after bootloader
                current_size = len(bootloader_data) + len(kernel_data)
                target_size = 512 + (16 * 512)  # Bootloader + 16 sectors
                if current_size < target_size:
                    out.write(bytes(target_size - current_size))
        
        return output_path
    
    def build_iso(self, output_path: str) -> str:
        """
        Build an ISO image for CD/USB boot.
        
        Args:
            output_path: Output file path
        
        Returns:
            Path to the built ISO.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Build binary first
            bin_path = tmpdir / "os.bin"
            self.build_bin(str(bin_path))
            
            # Create ISO directory structure
            iso_dir = tmpdir / "iso"
            boot_dir = iso_dir / "boot"
            grub_dir = boot_dir / "grub"
            grub_dir.mkdir(parents=True)
            
            # Copy kernel
            shutil.copy(bin_path, boot_dir / "kernel.bin")
            
            # Create GRUB config
            grub_cfg = grub_dir / "grub.cfg"
            grub_cfg.write_text("""
set timeout=0
set default=0

menuentry "pyOS" {
    multiboot /boot/kernel.bin
    boot
}
""")
            
            # Try to create ISO with grub-mkrescue
            if self._has_grub_mkrescue():
                self._create_iso_grub(iso_dir, output_path)
            else:
                # Fallback: just copy the binary
                shutil.copy(bin_path, output_path)
                print("Warning: grub-mkrescue not found, created raw binary instead of ISO")
        
        return output_path
    
    def _has_grub_mkrescue(self) -> bool:
        """Check if grub-mkrescue is available."""
        try:
            result = subprocess.run(
                ["grub-mkrescue", "--version"],
                capture_output=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def _create_iso_grub(self, iso_dir: Path, output_path: str) -> None:
        """Create ISO using grub-mkrescue."""
        cmd = [
            "grub-mkrescue",
            "-o", output_path,
            str(iso_dir),
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise BuildError(f"grub-mkrescue failed:\n{result.stderr}")
    
    def get_asm(self) -> str:
        """
        Get the generated Assembly code.
        
        Returns:
            Assembly source code.
        """
        from .compiler.codegen import CodeGenerator
        
        generator = CodeGenerator(self.kernel)
        return generator.generate()
    
    def save_asm(self, output_path: str) -> str:
        """
        Save generated Assembly to file.
        
        Args:
            output_path: Output file path
        
        Returns:
            Path to saved file.
        """
        asm = self.get_asm()
        
        with open(output_path, "w") as f:
            f.write(asm)
        
        return output_path
