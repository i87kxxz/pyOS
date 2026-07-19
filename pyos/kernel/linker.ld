ENTRY(_start)
OUTPUT_FORMAT(pei-i386)

SECTIONS
{
    /* Multiboot / QEMU -kernel load address (1 MiB). */
    . = 0x100000;

    .multiboot : {
        *(.multiboot)
    }

    .text : {
        *(.text)
        *(.text.*)
    }

    .rdata : {
        *(.rdata)
        *(.rdata.*)
        *(.rodata)
        *(.rodata.*)
    }

    .data : {
        *(.data)
        *(.data.*)
    }

    .bss : {
        __bss_start = .;
        *(.bss)
        *(.bss.*)
        *(COMMON)
        __bss_end = .;
    }
}
