/* Kernel entry — preprocessed by GCC (.S) */
.text
.global _start

#ifdef _WIN32
.extern _kmain
_start:
    movb $'M', %al
    outb %al, $0xE9
    call _kmain
#else
.extern kmain
_start:
    movb $'M', %al
    outb %al, $0xE9
    call kmain
#endif
1:
    cli
    hlt
    jmp 1b
