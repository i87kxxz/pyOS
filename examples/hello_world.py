"""
Hello World OS - minimal pyOS example
"""

from pyos import Kernel, Screen

kernel = Kernel(arch="x86")


@kernel.on_boot
def main():
    Screen.clear()
    Screen.set_color("green", "black")
    Screen.print("Hello World!")
    Screen.print("Welcome to pyOS!", row=1)
    Screen.set_color("white", "black")
    Screen.print("This OS was written in Python", row=3)
    Screen.print("and runs on a C + ASM kernel.", row=4)
    Screen.print("Red text", row=6, color="red")
    Screen.print("Blue text", row=7, color="blue")
    Screen.print("Yellow text", row=8, color="yellow")


if __name__ == "__main__":
    kernel.build("hello_world.bin")
    print("Built hello_world.bin")
    print("Run:  pyos run hello_world.bin")
    print("Debug: pyos debug hello_world.bin")
