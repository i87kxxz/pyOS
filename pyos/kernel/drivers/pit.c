#include "timer.h"
#include "io.h"
#include "kernel.h"
#include "task.h"

static volatile u32 g_ticks = 0;
static u32 g_hz = 100;
static u32 g_timer_div = 1;
static u32 g_timer_acc = 0;

void pit_init(u32 hz) {
    if (hz < 18) hz = 18;
    if (hz > 1000) hz = 1000;
    g_hz = hz;
    u32 divisor = 1193180u / hz;
    outb(0x43, 0x36);
    outb(0x40, (u8)(divisor & 0xFF));
    outb(0x40, (u8)((divisor >> 8) & 0xFF));
    g_ticks = 0;
    g_timer_acc = 0;
    if (g_kernel_config.timer_interval_ms == 0) {
        g_timer_div = 0;
    } else {
        g_timer_div = (g_kernel_config.timer_interval_ms * hz) / 1000u;
        if (g_timer_div == 0) g_timer_div = 1;
    }
}

void pit_irq(void) {
    g_ticks++;
    if (g_kernel_config.enable_processes) {
        task_on_timer();
    }
    if (g_kernel_config.has_timer_handler && g_timer_div) {
        g_timer_acc++;
        if (g_timer_acc >= g_timer_div) {
            g_timer_acc = 0;
            pyos_user_timer();
        }
    }
}

u32 timer_ticks(void) { return g_ticks; }

u32 timer_ms(void) {
    return (g_ticks * 1000u) / g_hz;
}

void timer_sleep_ms(u32 ms) {
    u32 start = timer_ms();
    while (timer_ms() - start < ms) {
        __asm__ volatile ("hlt");
    }
}
