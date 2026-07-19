#include "kernel.h"
#include "screen.h"
#include "keyboard.h"
#include "idt.h"
#include "pic.h"
#include "heap.h"
#include "syscall.h"
#include "debug.h"
#include "io.h"
#include "timer.h"
#include "gdt.h"
#include "paging.h"
#include "pmm.h"
#include "task.h"
#include "vfs.h"
#include "shell.h"
#include "floppy.h"

extern KernelConfig g_kernel_config;

__attribute__((weak)) void pyos_user_boot(void) {}
__attribute__((weak)) void pyos_user_keypress(char ch, u8 scancode) {
    (void)ch;
    (void)scancode;
}
__attribute__((weak)) void pyos_user_timer(void) {}

void kmain(void) {
    serial_init();
    debug_log("Booting pyOS C kernel...");

    screen_init();
    screen_clear();
    debug_log("VGA ready");

    if (g_kernel_config.enable_user_mode || g_kernel_config.enable_paging) {
        gdt_init();
        tss_set_kernel_stack(g_kernel_config.stack_top);
        debug_log("GDT+TSS loaded");
    }

    keyboard_init();
    heap_init(g_kernel_config.heap_start, g_kernel_config.heap_size);
    debug_log("Heap ready (free-list)");

    /* 16 MiB frame pool — enough for BusyBox (~1MiB) + stacks/page tables */
    pmm_init(g_kernel_config.heap_start + g_kernel_config.heap_size, 0x1000000);
    floppy_init();
    vfs_init();
    task_init();
    shell_init();

    if (g_kernel_config.enable_paging) {
        paging_init();
        debug_log("Paging enabled (identity map + CR3)");
    }

    if (g_kernel_config.enable_interrupts) {
        idt_init();
        debug_log("IDT loaded");
        pic_init();
        pit_init(100);
        syscall_init();
        sti();
        debug_log("Interrupts+PIT enabled");
    }

    debug_log("Running @kernel.on_boot handlers");
    pyos_user_boot();
    debug_log("Boot complete - idle");

    if (g_kernel_config.has_keypress_handler) {
        screen_print_at("> ", 23, 0, 0x0F);
    }

    for (;;) {
        hlt();
    }
}
