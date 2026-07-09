"""
Keyboard Input OS - interactive echo via @kernel.on_keypress
"""

from pyos import Kernel, Screen

kernel = Kernel(arch="x86")


@kernel.on_boot
def main():
    Screen.clear()
    Screen.set_color("cyan", "black")
    Screen.print("=================================", row=0)
    Screen.print("    Keyboard Demo OS - pyOS", row=1)
    Screen.print("=================================", row=2)
    Screen.set_color("white", "black")
    Screen.print("Type on the keyboard — keys echo below.", row=4)
    Screen.set_color("green", "black")
    Screen.print("[OK] Kernel loaded", row=6)
    Screen.print("[OK] IDT + PIC ready", row=7)
    Screen.print("[OK] Keyboard IRQ1 enabled", row=8)
    Screen.set_color("yellow", "black")
    Screen.print("Output:", row=10)


@kernel.on_keypress
def on_key(key=None):
    """Marks that this OS wants runtime keyboard handling."""
    pass


if __name__ == "__main__":
    kernel.build("keyboard.bin")
    print("Built keyboard.bin")
    print("Run: pyos run keyboard.bin")
