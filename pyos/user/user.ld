ENTRY(_start)
SECTIONS {
  . = 0x08048000;
  .text : {
    *(.text*)
    *(.rdata*)
    *(.rodata*)
    *(.data*)
    *(.bss*)
  }
}
