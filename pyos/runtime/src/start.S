/* Kernel entry — preprocessed by GCC (.S) */
.text
.global _start

#ifdef _WIN32
.extern _kmain
_start:
    call _kmain
#else
.extern kmain
_start:
    call kmain
#endif
1:
    cli
    hlt
    jmp 1b
