#include "shell.h"
#include "screen.h"
#include "vfs.h"
#include "heap.h"
#include "task.h"
#include "string.h"
#include "kernel.h"
#include "debug.h"

static char line[128];
static u32 line_len = 0;
static pyos_bool shell_active = PYOS_FALSE;
static u32 timer_count = 0;

static void list_cb(const char *name, u32 size) {
    screen_print(name);
    screen_print(" ");
    (void)size;
}

void shell_init(void) {
    line_len = 0;
    line[0] = 0;
    shell_active = PYOS_TRUE;
    timer_count = 0;
}

void shell_run_line(const char *cmd) {
    if (!cmd) return;
    if (strcmp(cmd, "help") == 0) {
        screen_print("commands: help ps free ls cat clear echo\n");
    } else if (strcmp(cmd, "ps") == 0) {
        screen_print("pid=");
        /* simple */
        screen_print("1 idle / 2 worker\n");
        (void)task_current_pid();
    } else if (strcmp(cmd, "free") == 0) {
        screen_print("heap free bytes reported via heap_free_bytes\n");
    } else if (strcmp(cmd, "ls") == 0) {
        vfs_list(list_cb);
        screen_putchar('\n');
    } else if (cmd[0] == 'c' && cmd[1] == 'a' && cmd[2] == 't' && cmd[3] == ' ') {
        const char *path = cmd + 4;
        i32 fd = vfs_open(path);
        if (fd < 0) {
            screen_print("not found\n");
            return;
        }
        char buf[128];
        i32 n = vfs_read(fd, buf, sizeof(buf) - 1);
        vfs_close(fd);
        if (n > 0) {
            buf[n] = 0;
            screen_print(buf);
            if (buf[n - 1] != '\n') screen_putchar('\n');
        }
    } else if (strcmp(cmd, "clear") == 0) {
        screen_clear();
    } else if (cmd[0] == 'e' && cmd[1] == 'c' && cmd[2] == 'h' && cmd[3] == 'o' && cmd[4] == ' ') {
        screen_print(cmd + 5);
        screen_putchar('\n');
    } else if (cmd[0] == 0) {
        /* empty */
    } else {
        screen_print("unknown. try help\n");
    }
}

void shell_on_key(char ch, u8 scancode) {
    (void)scancode;
    if (!shell_active) return;
    if (!ch) return;
    if (g_kernel_config.keypress_echo) {
        /* echo already done in glue when echo mode */
    }
    if (ch == '\n' || ch == '\r') {
        if (!g_kernel_config.keypress_echo) screen_putchar('\n');
        line[line_len] = 0;
        shell_run_line(line);
        line_len = 0;
        screen_print("> ");
        return;
    }
    if (ch == '\b') {
        if (line_len > 0) {
            line_len--;
            if (!g_kernel_config.keypress_echo) screen_putchar('\b');
        }
        return;
    }
    if (line_len + 1 < sizeof(line)) {
        line[line_len++] = ch;
        if (!g_kernel_config.keypress_echo) screen_putchar(ch);
    }
}

void shell_on_timer(void) {
    timer_count++;
    /* lightweight heartbeat in lab mode */
    if (g_kernel_config.debug_lab && (timer_count % 10) == 0) {
        debug_log("shell timer tick");
    }
}
