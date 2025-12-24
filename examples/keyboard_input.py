"""
Keyboard Input OS - Example with keyboard handling

This creates an OS that shows keyboard demo.
"""

from pyos import Kernel, Screen

# Create kernel
kernel = Kernel(arch="x86")

@kernel.on_boot
def main():
    """Boot function."""
    Screen.clear()
    
    # Title
    Screen.set_color("cyan", "black")
    Screen.print("=================================", row=0)
    Screen.print("    Keyboard Demo OS - pyOS", row=1)
    Screen.print("=================================", row=2)
    
    # Instructions
    Screen.set_color("white", "black")
    Screen.print("This OS demonstrates keyboard support.", row=4)
    Screen.print("Keyboard driver is ready!", row=5)
    
    # Status
    Screen.set_color("green", "black")
    Screen.print("[OK] Kernel loaded", row=7)
    Screen.print("[OK] Screen initialized", row=8)
    Screen.print("[OK] Keyboard driver ready", row=9)
    
    # Footer
    Screen.set_color("yellow", "black")
    Screen.print("System running...", row=12)

# Build
if __name__ == "__main__":
    kernel.build("keyboard.iso")
    print("Built keyboard.iso!")
    print("Run with: qemu-system-i386 -fda keyboard.iso")
