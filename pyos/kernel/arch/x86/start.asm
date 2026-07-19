; Kernel entry — Multiboot header + stack setup (NASM twin of start.S)
[BITS 32]

MULTIBOOT_MAGIC    equ 0x1BADB002
MULTIBOOT_FLAGS    equ 0x00000003
MULTIBOOT_CHECKSUM equ -(MULTIBOOT_MAGIC + MULTIBOOT_FLAGS)

section .multiboot
align 4
dd MULTIBOOT_MAGIC
dd MULTIBOOT_FLAGS
dd MULTIBOOT_CHECKSUM

section .text
global start
extern kmain

start:
    mov esp, 0x90000
    xor ebp, ebp
    mov al, 'M'
    out 0xE9, al
    call kmain
    cli
.hang:
    hlt
    jmp .hang
