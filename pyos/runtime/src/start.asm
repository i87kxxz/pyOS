; Kernel entry — first code at 0x1000
; NASM win32 auto-prefixes underscores to match MinGW COFF.
[BITS 32]
global start
extern kmain

start:
    call kmain
    cli
.hang:
    hlt
    jmp .hang
