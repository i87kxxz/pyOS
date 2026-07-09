"""
Keyboard + shell demo
"""

from pyos import Kernel, Screen

kernel = Kernel(arch="x86", enable_filesystem=True, enable_processes=True)

kernel.seed_file("motd.txt", "Welcome to pyOS shell\nTry: help ls cat motd.txt\n")


@kernel.on_boot
def main():
    Screen.clear()
    Screen.set_color("cyan", "black")
    Screen.print("pyOS Shell", row=0)
    Screen.print("Type help", row=1)


@kernel.on_keypress(mode="echo")
def on_key(key=None):
    pass


@kernel.on_timer(interval_ms=1000)
def tick():
    pass


if __name__ == "__main__":
    kernel.build("shell.bin")
    print("Built shell.bin — pyos run shell.bin")
