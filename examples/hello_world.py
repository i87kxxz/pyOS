"""
Hello World OS - Simple example using pyOS

This creates a minimal OS that displays "Hello World!" on screen.
"""

from pyos import Kernel, Screen

# Create a new kernel targeting x86 architecture
kernel = Kernel(arch="x86")

@kernel.on_boot
def main():
    """This function runs when the OS boots."""
    
    # Clear the screen
    Screen.clear()
    
    # Set text color to green on black background
    Screen.set_color("green", "black")
    
    # Print welcome message
    Screen.print("Hello World!")
    Screen.print("Welcome to pyOS!", row=1)
    
    # Change color and print more
    Screen.set_color("white", "black")
    Screen.print("This OS was written in Python", row=3)
    Screen.print("and compiled to Assembly!", row=4)
    
    # Print in different colors
    Screen.print("Red text", row=6, color="red")
    Screen.print("Blue text", row=7, color="blue")
    Screen.print("Yellow text", row=8, color="yellow")

# Build the OS
if __name__ == "__main__":
    kernel.build("hello_world.iso")
    print("Built hello_world.iso!")
    print("Run with: pyos run hello_world.iso")
