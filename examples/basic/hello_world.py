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
    Screen.print("This OS was written with a Python DSL", row=3)
    Screen.print("and runs on a real C + ASM kernel.", row=4)


if __name__ == "__main__":
    kernel.build("hello_world.bin")
    print("Built hello_world.bin")
    print("Run:  pyos run hello_world.bin")
