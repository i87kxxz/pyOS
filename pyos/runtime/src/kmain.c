#include "kernel.h"
#include "screen.h"
#include "keyboard.h"
#include "idt.h"
#include "pic.h"
#include "heap.h"
#include "syscall.h"
#include "debug.h"
#include "io.h"

/* Provided by generated glue.c — no weak duplicate */
extern KernelConfig g_kernel_config;

__attribute__((weak)) void pyos_user_boot(void) {}
__attribute__((weak)) void pyos_user_keypress(char ch, u8 scancode) {
    (void)ch;
    (void)scancode;
}

void kmain(void) {
    /* Bootloader already set ESP to 0x90000 — do not reload from data
       until .data is proven resident; avoids early faults. */
    serial_init();
    debug_log("Booting pyOS C runtime...");

    screen_init();
    screen_clear();
    debug_log("VGA ready");

    keyboard_init();
    heap_init(g_kernel_config.heap_start, g_kernel_config.heap_size);
    debug_log("Heap ready");

    if (g_kernel_config.enable_interrupts) {
        idt_init();
        debug_log("IDT loaded");
        pic_init();
        syscall_init();
        sti();
        debug_log("Interrupts enabled");
    }

    debug_log("Running @kernel.on_boot handlers");
    pyos_user_boot();
    debug_log("Boot complete - idle");

    for (;;) {
        hlt();
    }
}
