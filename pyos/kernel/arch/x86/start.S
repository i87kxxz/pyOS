/* Kernel entry — Multiboot (QEMU -kernel) + preprocessed for MinGW/Linux */
#define MULTIBOOT_MAGIC    0x1BADB002
#define MULTIBOOT_FLAGS    0x00000003  /* ALIGN | MEMORY_INFO */
#define MULTIBOOT_CHECKSUM -(MULTIBOOT_MAGIC + MULTIBOOT_FLAGS)

/* Must appear within the first 8 KiB of the Multiboot image. */
.section .multiboot, "a"
.align 4
.long MULTIBOOT_MAGIC
.long MULTIBOOT_FLAGS
.long MULTIBOOT_CHECKSUM

.text
.global _start

#ifdef _WIN32
.extern _kmain
_start:
    /* Multiboot does not provide a stack; use classic low-memory top. */
    movl $0x90000, %esp
    xorl %ebp, %ebp
    movb $'M', %al
    outb %al, $0xE9
    call _kmain
#else
.extern kmain
_start:
    movl $0x90000, %esp
    xorl %ebp, %ebp
    movb $'M', %al
    outb %al, $0xE9
    call kmain
#endif
1:
    cli
    hlt
    jmp 1b
