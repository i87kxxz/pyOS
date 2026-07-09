#include "syscall.h"
#include "screen.h"
#include "keyboard.h"
#include "debug.h"
#include "io.h"
#include "heap.h"
#include "timer.h"
#include "task.h"
#include "vfs.h"
#include "usercopy.h"
#include "kernel.h"

i32 syscall_dispatch(u32 num, u32 a1, u32 a2, u32 a3) {
    switch (num) {
    case SYS_EXIT:
        if (g_kernel_config.enable_processes) {
            task_exit((i32)a1);
            return 0;
        }
        debug_log("SYS_EXIT — halting");
        cli();
        for (;;) hlt();
        return 0;
    case SYS_WRITE: {
        if (a1 != 1) return -1;
        if (a3 > 4096) return -1;
        if (g_kernel_config.enable_user_mode) {
            char tmp[256];
            u32 left = a3;
            u32 off = 0;
            while (left) {
                u32 chunk = left > sizeof(tmp) ? (u32)sizeof(tmp) : left;
                if (copy_from_user(tmp, a2 + off, chunk) != 0) return -1;
                for (u32 i = 0; i < chunk; i++) screen_putchar(tmp[i]);
                left -= chunk;
                off += chunk;
            }
        } else {
            const char *buf = (const char *)a2;
            for (u32 i = 0; i < a3; i++) screen_putchar(buf[i]);
        }
        return (i32)a3;
    }
    case SYS_READ: {
        if (a1 != 0 || a3 == 0) return -1;
        if (!keyboard_has_key()) return 0;
        char ch = keyboard_read_char();
        if (g_kernel_config.enable_user_mode) {
            if (copy_to_user(a2, &ch, 1) != 0) return -1;
        } else {
            ((char *)a2)[0] = ch;
        }
        return 1;
    }
    case SYS_OPEN:
        return vfs_open((const char *)a1);
    case SYS_CLOSE:
        return vfs_close((i32)a1);
    case SYS_GETPID:
        return (i32)task_current_pid();
    case SYS_MALLOC:
        return (i32)(u32)heap_malloc(a1);
    case SYS_FREE:
        heap_free((void *)a1);
        return 0;
    case SYS_SLEEP:
        timer_sleep_ms(a1);
        return 0;
    case SYS_TIME:
        return (i32)timer_ms();
    case SYS_YIELD:
        task_schedule();
        return 0;
    case SYS_SPAWN:
        return task_spawn((const char *)a1, a2, a3);
    default:
        debug_log("Unknown syscall number");
        return -1;
    }
}

void syscall_init(void) {
    debug_log("Syscall gate int 0x80 ready");
}
