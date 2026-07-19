/*
 * Minimal ash-like init/shell for pyOS userland (freestanding i386).
 * Builtins: echo, ls, uname, help, exit. Falls back to /bin/busybox for others.
 */
typedef unsigned int u32;
typedef int i32;

#define SYS_EXIT   1
#define SYS_FORK   2
#define SYS_READ   3
#define SYS_WRITE  4
#define SYS_OPEN   5
#define SYS_CLOSE  6
#define SYS_WAITPID 7
#define SYS_EXECVE 11
#define SYS_GETDENTS 141
#define SYS_UNAME  109

struct utsname {
    char sysname[65];
    char nodename[65];
    char release[65];
    char version[65];
    char machine[65];
    char domainname[65];
};

struct linux_dirent {
    u32 d_ino;
    u32 d_off;
    unsigned short d_reclen;
    char d_name[];
};

static i32 syscall3(u32 n, u32 a, u32 b, u32 c) {
    i32 ret;
    __asm__ volatile("int $0x80" : "=a"(ret) : "a"(n), "b"(a), "c"(b), "d"(c) : "memory");
    return ret;
}

static i32 syscall1(u32 n, u32 a) {
    i32 ret;
    __asm__ volatile("int $0x80" : "=a"(ret) : "a"(n), "b"(a) : "memory");
    return ret;
}

static u32 strlen(const char *s) {
    u32 n = 0;
    if (!s) return 0;
    while (s[n]) n++;
    return n;
}

static void write_str(const char *s) {
    if (!s) return;
    syscall3(SYS_WRITE, 1, (u32)s, strlen(s));
}

static i32 streq(const char *a, const char *b) {
    if (!a || !b) return 0;
    while (*a && *b && *a == *b) {
        a++;
        b++;
    }
    return *a == 0 && *b == 0;
}

static i32 starts_with(const char *s, const char *p) {
    while (*p) {
        if (*s++ != *p++) return 0;
    }
    return 1;
}

static void cmd_echo(const char *arg) {
    if (arg) write_str(arg);
    write_str("\n");
}

static void cmd_uname(void) {
    struct utsname u;
    u32 i;
    for (i = 0; i < sizeof(u); i++) ((char *)&u)[i] = 0;
    if (syscall1(SYS_UNAME, (u32)&u) == 0) {
        write_str(u.sysname);
        write_str(" ");
        write_str(u.nodename);
        write_str(" ");
        write_str(u.release);
        write_str(" ");
        write_str(u.machine);
        write_str("\n");
    } else {
        write_str("uname: failed\n");
    }
}

static void cmd_ls(const char *path) {
    char buf[512];
    i32 fd;
    i32 n;
    if (!path || !path[0]) path = "/";
    fd = syscall3(SYS_OPEN, (u32)path, 0, 0);
    if (fd < 0) {
        write_str("ls: cannot open\n");
        return;
    }
    for (;;) {
        n = syscall3(SYS_GETDENTS, (u32)fd, (u32)buf, sizeof(buf));
        if (n <= 0) break;
        {
            i32 pos = 0;
            while (pos < n) {
                struct linux_dirent *de = (struct linux_dirent *)(buf + pos);
                if (de->d_reclen < 8) break;
                if (de->d_name[0] && !(de->d_name[0] == '.' && de->d_name[1] == 0)) {
                    write_str(de->d_name);
                    write_str("\n");
                }
                pos += de->d_reclen;
            }
        }
    }
    syscall1(SYS_CLOSE, (u32)fd);
}

static void skip_ws(const char **p) {
    while (**p == ' ' || **p == '\t') (*p)++;
}

static void run_line(const char *line) {
    char cmd[64];
    char argbuf[128];
    const char *p = line;
    u32 i = 0;
    skip_ws(&p);
    if (*p == 0) return;
    while (*p && *p != ' ' && *p != '\t' && i + 1 < sizeof(cmd)) cmd[i++] = *p++;
    cmd[i] = 0;
    skip_ws(&p);
    i = 0;
    while (*p && i + 1 < sizeof(argbuf)) argbuf[i++] = *p++;
    argbuf[i] = 0;

    if (streq(cmd, "echo")) {
        cmd_echo(argbuf);
    } else if (streq(cmd, "uname")) {
        cmd_uname();
    } else if (streq(cmd, "ls")) {
        cmd_ls(argbuf[0] ? argbuf : "/");
    } else if (streq(cmd, "help")) {
        write_str("builtins: echo ls uname help exit\n");
        write_str("or: busybox <applet> ...\n");
    } else if (streq(cmd, "exit")) {
        syscall1(SYS_EXIT, 0);
    } else if (streq(cmd, "busybox") || starts_with(cmd, "/bin/busybox")) {
        /* Best-effort: fork+exec busybox with remaining args as single argv1 */
        i32 pid = syscall1(SYS_FORK, 0);
        if (pid == 0) {
            const char *argv[4];
            argv[0] = "/bin/busybox";
            if (argbuf[0]) {
                /* first token of argbuf is applet name */
                char applet[32];
                u32 j = 0;
                const char *q = argbuf;
                while (*q && *q != ' ' && j + 1 < sizeof(applet)) applet[j++] = *q++;
                applet[j] = 0;
                argv[1] = applet;
                skip_ws(&q);
                argv[2] = *q ? q : 0;
                argv[3] = 0;
            } else {
                argv[1] = 0;
            }
            syscall3(SYS_EXECVE, (u32)"/bin/busybox", (u32)argv, 0);
            write_str("exec busybox failed\n");
            syscall1(SYS_EXIT, 1);
        } else if (pid > 0) {
            i32 st = 0;
            syscall3(SYS_WAITPID, (u32)pid, (u32)&st, 0);
        } else {
            write_str("fork failed\n");
        }
    } else {
        write_str("unknown command: ");
        write_str(cmd);
        write_str("\n");
    }
}

static void demo_fork_wait(void) {
    i32 pid = syscall1(SYS_FORK, 0);
    if (pid == 0) {
        write_str("fork-child-ok\n");
        syscall1(SYS_EXIT, 0);
    } else if (pid > 0) {
        i32 st = 0;
        syscall3(SYS_WAITPID, (u32)pid, (u32)&st, 0);
        write_str("fork-parent-ok\n");
    } else {
        write_str("fork failed\n");
    }
}

static void run_demo(void) {
    write_str("echo hello from pyOS\n");
    cmd_echo("hello from pyOS");
    write_str("uname\n");
    cmd_uname();
    write_str("ls /\n");
    cmd_ls("/");
    /* Linux i386 fork + waitpid (execve covered by /init and hi ELF tests). */
    write_str("fork demo\n");
    demo_fork_wait();
}

void _start(void) {
    char line[128];
    u32 len = 0;

    write_str("\nBusyBox v1.35.0 (pyOS ash)\n");
    write_str("Type help for builtins.\n");
    run_demo();
    write_str("# ");

    for (;;) {
        char ch = 0;
        i32 n = syscall3(SYS_READ, 0, (u32)&ch, 1);
        if (n <= 0) {
            /* No input yet — yield-ish by looping; PIT will schedule. */
            __asm__ volatile("pause");
            continue;
        }
        if (ch == '\r') ch = '\n';
        if (ch == '\n') {
            write_str("\n");
            line[len] = 0;
            run_line(line);
            len = 0;
            write_str("# ");
            continue;
        }
        if (ch == 0x08 || ch == 0x7f) {
            if (len) {
                len--;
                write_str("\b \b");
            }
            continue;
        }
        if (len + 1 < sizeof(line) && ch >= 32) {
            line[len++] = ch;
            syscall3(SYS_WRITE, 1, (u32)&ch, 1);
        }
    }
}
