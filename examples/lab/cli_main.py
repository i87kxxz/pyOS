from pyos import Kernel, Screen
k=Kernel()
@k.on_boot
def m():
    Screen.print("cli")
