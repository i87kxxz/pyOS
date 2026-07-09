"""
Advanced OS — paging, processes, filesystem, timer
"""

from pyos import Kernel, Screen, Memory

kernel = Kernel(
    arch="x86",
    stack_size=32768,
    heap_size=2 * 1024 * 1024,
    enable_paging=True,
    enable_user_mode=True,
    enable_processes=True,
    enable_filesystem=True,
)

kernel.seed_file("motd.txt", "Advanced pyOS 1.0\n")


@kernel.on_boot(priority=0)
def banner():
    Screen.clear()
    Screen.set_color("light_cyan", "black")
    Screen.print("pyOS Advanced", row=0)
    Screen.print("paging+tasks+vfs", row=1)


@kernel.on_boot(priority=1)
def mem():
    p = Memory.malloc(256)
    Memory.memset(p, 0, 256)
    Memory.free(p)
    Screen.print("heap ok", row=3, color="green")


@kernel.on_keypress
def on_key(key=None):
    pass


@kernel.on_timer(interval_ms=500)
def tick():
    pass


if __name__ == "__main__":
    kernel.build("advanced_os.bin")
    print("Built advanced_os.bin")
