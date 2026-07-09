ENTRY(_start)
OUTPUT_FORMAT(pei-i386)

SECTIONS
{
    /* Force low addresses; MinGW PE image base overridden via ld flags */
    . = 0x1000;

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
