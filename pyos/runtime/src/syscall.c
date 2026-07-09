#include "syscall.h"
#include "screen.h"
#include "keyboard.h"
#include "debug.h"
#include "io.h"

i32 syscall_dispatch(u32 num, u32 a1, u32 a2, u32 a3) {
    switch (num) {
    case SYS_EXIT:
        debug_log("SYS_EXIT called — halting CPU");
        cli();
        for (;;) hlt();
        return 0;
    case SYS_WRITE: {
        /* a1=fd (1=stdout), a2=buf, a3=len */
        const char *buf = (const char *)a2;
        u32 len = a3;
        if (a1 != 1) {
            debug_log("SYS_WRITE: only fd=1 (stdout) is supported");
            return -1;
        }
        for (u32 i = 0; i < len; i++) {
            screen_putchar(buf[i]);
        }
        return (i32)len;
    }
    case SYS_READ: {
        /* a1=fd (0=stdin), a2=buf, a3=len — read one char if available */
        char *buf = (char *)a2;
        if (a1 != 0 || a3 == 0) return -1;
        if (!keyboard_has_key()) return 0;
        buf[0] = keyboard_read_char();
        return 1;
    }
    default:
        debug_log("Unknown syscall number");
        return -1;
    }
}

void syscall_init(void) {
    debug_log("Syscall gate int 0x80 ready (WRITE/READ/EXIT)");
}
