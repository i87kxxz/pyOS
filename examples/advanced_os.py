"""
Advanced OS Example - Full featured OS with pyOS

Demonstrates:
- Multiple boot stages
- Colorful UI
- System information display
- Memory info
"""

from pyos import Kernel, Screen

# Create kernel with all features enabled
kernel = Kernel(
    arch="x86",
    stack_size=32768,      # 32KB stack
    heap_size=4194304,     # 4MB heap
)

@kernel.on_boot(priority=0)
def boot_stage1():
    """First boot stage - clear and show logo."""
    Screen.clear()
    
    # ASCII Art Logo
    Screen.set_color("light_cyan", "black")
    Screen.print("  ____        ___  ____  ", row=0)
    Screen.print(" |  _ \\ _   _/ _ \\/ ___| ", row=1)
    Screen.print(" | |_) | | | | | | \\___ \\ ", row=2)
    Screen.print(" |  __/| |_| | |_| |___) |", row=3)
    Screen.print(" |_|    \\__, |\\___/|____/ ", row=4)
    Screen.print("        |___/             ", row=5)

@kernel.on_boot(priority=1)
def boot_stage2():
    """Second boot stage - show version."""
    Screen.set_color("white", "black")
    Screen.print("Advanced Operating System v1.0", row=7)
    Screen.print("Built with pyOS Framework", row=8)

@kernel.on_boot(priority=2)
def boot_stage3():
    """Third boot stage - system info."""
    Screen.set_color("green", "black")
    Screen.print("[*] Initializing system...", row=10)
    
    Screen.print("[OK] CPU: x86 Protected Mode", row=11)
    Screen.print("[OK] Memory: 4MB Heap Available", row=12)
    Screen.print("[OK] Stack: 32KB Allocated", row=13)
    Screen.print("[OK] VGA: 80x25 Text Mode", row=14)

@kernel.on_boot(priority=3)
def boot_stage4():
    """Fourth boot stage - ready message."""
    Screen.set_color("yellow", "black")
    Screen.print("========================================", row=16)
    Screen.print("         System Ready!", row=17)
    Screen.print("========================================", row=18)
    
    # Color demo
    Screen.print("Color Demo:", row=20, color="white")
    Screen.print("RED", row=21, col=0, color="red")
    Screen.print("GREEN", row=21, col=5, color="green")
    Screen.print("BLUE", row=21, col=12, color="blue")
    Screen.print("YELLOW", row=21, col=18, color="yellow")
    Screen.print("CYAN", row=21, col=26, color="cyan")
    Screen.print("MAGENTA", row=21, col=32, color="magenta")
    
    Screen.set_color("light_gray", "black")
    Screen.print("Kernel halted. System stable.", row=24)

# Build
if __name__ == "__main__":
    kernel.build("advanced_os.iso")
    print("Built advanced_os.iso!")
    print("Run with: qemu-system-i386 -fda advanced_os.iso")
