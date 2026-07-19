#ifndef PYOS_KERNEL_H
#define PYOS_KERNEL_H

#include "types.h"

typedef struct {
    u32 stack_top;
    u32 stack_size;
    u32 heap_start;
    u32 heap_size;
    pyos_bool enable_interrupts;
    pyos_bool has_keypress_handler;
    pyos_bool has_timer_handler;
    u32 timer_interval_ms;
    pyos_bool enable_paging;
    pyos_bool enable_user_mode;
    pyos_bool enable_processes;
    pyos_bool enable_filesystem;
    pyos_bool enable_network;
    pyos_bool debug_lab;
    pyos_bool keypress_echo;
} KernelConfig;

extern KernelConfig g_kernel_config;

void pyos_user_boot(void);
void pyos_user_keypress(char ch, u8 scancode);
void pyos_user_timer(void);

void kmain(void);

#endif
