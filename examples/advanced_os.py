"""
Advanced OS Example - multi-stage boot with pyOS
"""

from pyos import Kernel, Screen

kernel = Kernel(
    arch="x86",
    stack_size=32768,
    heap_size=4194304,
)


@kernel.on_boot(priority=0)
def boot_stage1():
    Screen.clear()
    Screen.set_color("light_cyan", "black")
    Screen.print("  ____        ___  ____  ", row=0)
    Screen.print(" |  _ \\ _   _/ _ \\/ ___| ", row=1)
    Screen.print(" | |_) | | | | | | \\___ \\ ", row=2)
    Screen.print(" |  __/| |_| | |_| |___) |", row=3)
    Screen.print(" |_|    \\__, |\\___/|____/ ", row=4)
    Screen.print("        |___/             ", row=5)


@kernel.on_boot(priority=1)
def boot_stage2():
    Screen.set_color("white", "black")
    Screen.print("Advanced Operating System v1.0", row=7)
    Screen.print("Python API  |  C runtime  |  ASM boot", row=8)


@kernel.on_boot(priority=2)
def boot_stage3():
    Screen.set_color("green", "black")
    Screen.print("[*] Initializing system...", row=10)
    Screen.print("[OK] CPU: x86 Protected Mode", row=11)
    Screen.print("[OK] Memory: 4MB Heap Available", row=12)
    Screen.print("[OK] Interrupts: IDT + PIC", row=13)
    Screen.print("[OK] VGA: 80x25 Text Mode", row=14)


@kernel.on_boot(priority=3)
def boot_stage4():
    Screen.set_color("yellow", "black")
    Screen.print("========================================", row=16)
    Screen.print("         System Ready!", row=17)
    Screen.print("========================================", row=18)
    Screen.print("Color Demo:", row=20, color="white")
    Screen.print("RED", row=21, col=0, color="red")
    Screen.print("GREEN", row=21, col=5, color="green")
    Screen.print("BLUE", row=21, col=12, color="blue")
    Screen.print("YELLOW", row=21, col=18, color="yellow")
    Screen.set_color("light_gray", "black")
    Screen.print("Idle. Open serial with: pyos debug advanced_os.bin", row=23)


if __name__ == "__main__":
    kernel.build("advanced_os.bin")
    print("Built advanced_os.bin")
    print("Run: qemu-system-i386 -fda advanced_os.bin")
