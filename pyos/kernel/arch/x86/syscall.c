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
#include "paging.h"
#include "string.h"
#include "pmm.h"
#include "socket.h"
#include "net.h"

/* Linux ioctl / termios stubs */
#define TCGETS 0x5401u
#define TCSETS 0x5402u
#define TIOCGWINSZ 0x5413u

/* Minimal Linux i386 structs (partial). */
struct linux_stat {
    u32 st_dev;
    u32 st_ino;
    u16 st_mode;
    u16 st_nlink;
    u16 st_uid;
    u16 st_gid;
    u32 st_rdev;
    u32 st_size;
    u32 st_blksize;
    u32 st_blocks;
    u32 st_atime;
    u32 st_atime_nsec;
    u32 st_mtime;
    u32 st_mtime_nsec;
    u32 st_ctime;
    u32 st_ctime_nsec;
    u32 __unused4;
    u32 __unused5;
};

struct linux_utsname {
    char sysname[65];
    char nodename[65];
    char release[65];
    char version[65];
    char machine[65];
    char domainname[65];
};

struct linux_timespec {
    i32 tv_sec;
    i32 tv_nsec;
};

static void put_user_str(char *dst, const char *src, u32 n) {
    u32 i = 0;
    if (!dst || n == 0) return;
    for (; i + 1 < n && src[i]; i++) dst[i] = src[i];
    dst[i] = 0;
}

static i32 sys_write(u32 fd, u32 buf, u32 len) {
    if (fd == 1 || fd == 2) {
        if (len > 4096) return -1;
        if (g_kernel_config.enable_user_mode) {
            char tmp[256];
            u32 left = len;
            u32 off = 0;
            while (left) {
                u32 chunk = left > sizeof(tmp) ? (u32)sizeof(tmp) : left;
                if (copy_from_user(tmp, buf + off, chunk) != 0) return -1;
                for (u32 i = 0; i < chunk; i++) {
                    screen_putchar(tmp[i]);
                    serial_write(tmp[i]);
                }
                left -= chunk;
                off += chunk;
            }
        } else {
            const char *p = (const char *)buf;
            for (u32 i = 0; i < len; i++) {
                screen_putchar(p[i]);
                serial_write(p[i]);
            }
        }
        return (i32)len;
    }
    /* File write via VFS */
    if (len > 4096) return -1;
    char kbuf[256];
    u32 left = len;
    u32 off = 0;
    i32 total = 0;
    while (left) {
        u32 chunk = left > sizeof(kbuf) ? (u32)sizeof(kbuf) : left;
        if (g_kernel_config.enable_user_mode) {
            if (copy_from_user(kbuf, buf + off, chunk) != 0) return -1;
        } else {
            memcpy(kbuf, (const void *)(buf + off), chunk);
        }
        i32 n = vfs_write((i32)fd, kbuf, chunk);
        if (n < 0) return total ? total : -1;
        total += n;
        if ((u32)n < chunk) break;
        left -= chunk;
        off += chunk;
    }
    return total;
}

static i32 sys_read(u32 fd, u32 buf, u32 len) {
    if (fd == 0) {
        if (len == 0) return 0;
        /* Prefer serial (QEMU tests / interactive), then keyboard. */
        char ch = 0;
        pyos_bool got = PYOS_FALSE;
        if (serial_can_read()) {
            i32 c = serial_read();
            if (c >= 0) {
                ch = (char)c;
                got = PYOS_TRUE;
            }
        }
        if (!got && keyboard_has_key()) {
            ch = keyboard_read_char();
            got = PYOS_TRUE;
        }
        if (!got) return 0;
        if (g_kernel_config.enable_user_mode) {
            if (copy_to_user(buf, &ch, 1) != 0) return -1;
        } else {
            ((char *)buf)[0] = ch;
        }
        return 1;
    }
    /* File read via VFS */
    if (len == 0 || len > 4096) return -1;
    char kbuf[256];
    u32 left = len;
    u32 off = 0;
    i32 total = 0;
    while (left) {
        u32 chunk = left > sizeof(kbuf) ? (u32)sizeof(kbuf) : left;
        i32 n = vfs_read((i32)fd, kbuf, chunk);
        if (n < 0) return total ? total : -1;
        if (n == 0) break;
        if (g_kernel_config.enable_user_mode) {
            if (copy_to_user(buf + off, kbuf, (u32)n) != 0) return -1;
        } else {
            memcpy((void *)(buf + off), kbuf, (u32)n);
        }
        total += n;
        off += (u32)n;
        left -= (u32)n;
        if ((u32)n < chunk) break;
    }
    return total;
}

static i32 sys_brk(u32 addr) {
    Task *t = task_current();
    if (!t) return 0;
    if (addr == 0) return (i32)t->brk;
    if (addr < t->brk) {
        /* Shrink not fully implemented — just move pointer. */
        t->brk = addr;
        return (i32)t->brk;
    }
    if (paging_enabled() && t->cr3) {
        u32 old = t->brk;
        if (paging_map_anon_user(t->cr3, old, addr - old, PAGE_PRESENT | PAGE_RW | PAGE_USER) != 0) {
            return (i32)t->brk;
        }
    }
    t->brk = addr;
    return (i32)t->brk;
}

static i32 sys_mmap2(u32 addr, u32 len, u32 prot, u32 flags, u32 fd, u32 pgoff) {
    (void)prot;
    (void)flags;
    (void)fd;
    (void)pgoff;
    Task *t = task_current();
    if (!t || !paging_enabled() || !t->cr3) return -1;
    if (len == 0) return -1;
    u32 va = addr;
    if (va == 0) {
        va = t->mmap_hint;
        t->mmap_hint = (va + len + PAGE_SIZE - 1) & ~(PAGE_SIZE - 1);
    }
    if (paging_map_anon_user(t->cr3, va, len, PAGE_PRESENT | PAGE_RW | PAGE_USER) != 0) return -1;
    return (i32)va;
}

static i32 sys_munmap(u32 addr, u32 len) {
    Task *t = task_current();
    if (!t || !t->cr3 || len == 0) return -1;
    u32 start = addr & ~(PAGE_SIZE - 1);
    u32 end = (addr + len + PAGE_SIZE - 1) & ~(PAGE_SIZE - 1);
    for (u32 va = start; va < end; va += PAGE_SIZE) {
        if (!paging_is_mapped(t->cr3, va)) continue;
        u32 phys = paging_virt_to_phys(t->cr3, va);
        paging_unmap_page(t->cr3, va);
        if (phys) pmm_free_page((void *)(phys & ~(PAGE_SIZE - 1)));
    }
    return 0;
}

static i32 sys_stat_path(const char *path, u32 user_stat) {
    char kpath[64];
    if (g_kernel_config.enable_user_mode) {
        if (copy_from_user(kpath, (u32)(uintptr_t)path, sizeof(kpath) - 1) != 0) return -1;
        kpath[sizeof(kpath) - 1] = 0;
        path = kpath;
    }
    VfsPathInfo info;
    struct linux_stat st;
    memset(&st, 0, sizeof(st));
    if (vfs_resolve(path, &info) != 0 || !info.found) {
        return -1;
    }
    if ((info.mode & 0xF000u) == 0x4000u || (path && path[0] == '/' && path[1] == 0)) {
        st.st_mode = info.mode ? info.mode : 0040755;
        st.st_nlink = 1;
    } else {
        st.st_mode = info.mode ? info.mode : 0100644;
        st.st_nlink = 1;
        st.st_size = info.size;
        st.st_blksize = 1024;
        st.st_blocks = (st.st_size + 511) / 512;
        st.st_ino = info.ino ? info.ino : (u32)(info.ram_idx + 1);
    }
    if (g_kernel_config.enable_user_mode) {
        if (copy_to_user(user_stat, &st, sizeof(st)) != 0) return -1;
    } else {
        memcpy((void *)user_stat, &st, sizeof(st));
    }
    return 0;
}

i32 syscall_handler_c(u32 num, u32 a1, u32 a2, u32 a3, u32 a4, u32 a5, u32 a6) {
    return syscall_dispatch(num, a1, a2, a3, a4, a5, a6);
}

i32 syscall_dispatch(u32 num, u32 a1, u32 a2, u32 a3, u32 a4, u32 a5, u32 a6) {
    switch (num) {
    case SYS_EXIT:
    case SYS_EXIT_GROUP:
        if (g_kernel_config.enable_processes) {
            task_exit((i32)a1);
            return 0;
        }
        debug_log("SYS_EXIT — halting");
        cli();
        for (;;) hlt();
        return 0;

    case SYS_FORK:
        return task_fork();

    case SYS_READ:
        return sys_read(a1, a2, a3);

    case SYS_WRITE:
        return sys_write(a1, a2, a3);

    case SYS_OPEN: {
        char kpath[64];
        const char *path = (const char *)a1;
        if (g_kernel_config.enable_user_mode) {
            if (copy_from_user(kpath, a1, sizeof(kpath) - 1) != 0) return -1;
            kpath[sizeof(kpath) - 1] = 0;
            path = kpath;
        }
        return vfs_open_flags(path, a2);
    }

    case SYS_CLOSE:
        if (sock_is_socket((i32)a1)) return sock_close((i32)a1);
        return vfs_close((i32)a1);

    case SYS_WAITPID:
    case SYS_WAIT4: {
        i32 status = 0;
        i32 r = task_waitpid((i32)a1, &status, (i32)a3);
        if (a2) {
            if (g_kernel_config.enable_user_mode) {
                if (copy_to_user(a2, &status, sizeof(status)) != 0) return -1;
            } else {
                *(i32 *)a2 = status;
            }
        }
        (void)a4;
        (void)a5;
        (void)a6;
        return r;
    }

    case SYS_EXECVE: {
        char kpath[64];
        const char *path = (const char *)a1;
        if (g_kernel_config.enable_user_mode) {
            if (copy_from_user(kpath, a1, sizeof(kpath) - 1) != 0) return -1;
            kpath[sizeof(kpath) - 1] = 0;
            path = kpath;
        }
        return task_execve(path, a2, a3);
    }

    case SYS_CHDIR: {
        Task *t = task_current();
        if (!t) return -1;
        char kpath[TASK_CWD_LEN];
        if (g_kernel_config.enable_user_mode) {
            if (copy_from_user(kpath, a1, sizeof(kpath) - 1) != 0) return -1;
            kpath[sizeof(kpath) - 1] = 0;
        } else {
            strncpy(kpath, (const char *)a1, sizeof(kpath) - 1);
            kpath[sizeof(kpath) - 1] = 0;
        }
        strncpy(t->cwd, kpath, TASK_CWD_LEN - 1);
        t->cwd[TASK_CWD_LEN - 1] = 0;
        return 0;
    }

    case SYS_TIME: {
        u32 secs = timer_ms() / 1000u;
        if (a1) {
            if (g_kernel_config.enable_user_mode) {
                if (copy_to_user(a1, &secs, 4) != 0) return -1;
            } else {
                *(u32 *)a1 = secs;
            }
        }
        return (i32)secs;
    }

    case SYS_GETPID:
        return (i32)task_current_pid();

    case SYS_GETUID:
    case SYS_GETGID:
    case SYS_GETEUID:
    case SYS_GETEGID:
        return 0;

    case SYS_GETPPID: {
        Task *t = task_current();
        return t ? (i32)t->ppid : 0;
    }

    case SYS_ACCESS:
    case SYS_FACCESSAT: {
        char kpath[64];
        u32 path_arg = (num == SYS_FACCESSAT) ? a2 : a1;
        const char *path = (const char *)(uintptr_t)path_arg;
        if (g_kernel_config.enable_user_mode) {
            if (copy_from_user(kpath, path_arg, sizeof(kpath) - 1) != 0) return -1;
            kpath[sizeof(kpath) - 1] = 0;
            path = kpath;
        }
        VfsPathInfo info;
        if (vfs_resolve(path, &info) != 0 || !info.found) return -1;
        return 0;
    }

    case SYS_OPENAT: {
        char kpath[64];
        const char *path = (const char *)(uintptr_t)a2;
        if (g_kernel_config.enable_user_mode) {
            if (copy_from_user(kpath, a2, sizeof(kpath) - 1) != 0) return -1;
            kpath[sizeof(kpath) - 1] = 0;
            path = kpath;
        }
        (void)a1; /* dirfd ignored — absolute paths only for now */
        return vfs_open_flags(path, a3);
    }

    case SYS_GETDENTS:
    case SYS_GETDENTS64: {
        char kbuf[512];
        u32 len = a3;
        if (len > sizeof(kbuf)) len = sizeof(kbuf);
        i32 n = vfs_getdents((i32)a1, kbuf, len);
        if (n <= 0) return n;
        if (g_kernel_config.enable_user_mode) {
            if (copy_to_user(a2, kbuf, (u32)n) != 0) return -1;
        } else {
            memcpy((void *)(uintptr_t)a2, kbuf, (u32)n);
        }
        return n;
    }

    case SYS_SET_THREAD_AREA:
        /* musl TLS: accept and pretend success (GDT TLS not wired yet). */
        return 0;

    case SYS_UGETRLIMIT:
        return -1;

    case SYS_DUP:
    case SYS_DUP2:
        /* Honest stub: success with same/new fd number. */
        return (num == SYS_DUP2) ? (i32)a2 : ((i32)a1 + 1);

    case SYS_PIPE: {
        i32 fds[2] = {3, 4};
        if (g_kernel_config.enable_user_mode) {
            if (copy_to_user(a1, fds, sizeof(fds)) != 0) return -1;
        } else {
            ((i32 *)a1)[0] = fds[0];
            ((i32 *)a1)[1] = fds[1];
        }
        return 0;
    }

    case SYS_BRK:
        return sys_brk(a1);

    case SYS_IOCTL:
        if (a2 == TCGETS || a2 == TCSETS || a2 == TIOCGWINSZ) return 0;
        return 0;

    case SYS_FCNTL:
        return 0;

    case SYS_MMAP:
    case SYS_MMAP2:
        return sys_mmap2(a1, a2, a3, a4, a5, a6);

    case SYS_MUNMAP:
        return sys_munmap(a1, a2);

    case SYS_SOCKETCALL:
        return sock_socketcall(a1, a2);

    case SYS_SELECT:
        return sock_select((i32)a1, (void *)(uintptr_t)a2, (void *)(uintptr_t)a3,
                           (void *)(uintptr_t)a4, (void *)(uintptr_t)a5);

    case SYS_POLL: {
        /* struct pollfd { int fd; short events; short revents; } */
        struct {
            i32 fd;
            i16 events;
            i16 revents;
        } pf;
        if (!a1 || a2 < 1) return 0;
        if (g_kernel_config.enable_user_mode) {
            if (copy_from_user(&pf, a1, sizeof(pf)) != 0) return -1;
        } else {
            memcpy(&pf, (void *)(uintptr_t)a1, sizeof(pf));
        }
        i32 r = sock_poll(pf.fd, pf.events, (i32)a3);
        pf.revents = r > 0 ? pf.events : 0;
        if (g_kernel_config.enable_user_mode) {
            if (copy_to_user(a1, &pf, sizeof(pf)) != 0) return -1;
        } else {
            memcpy((void *)(uintptr_t)a1, &pf, sizeof(pf));
        }
        return r;
    }

    case SYS_MPROTECT:
        return 0;

    case SYS_STAT:
    case SYS_LSTAT:
        return sys_stat_path((const char *)(uintptr_t)a1, a2);

    case SYS_FSTAT: {
        struct linux_stat st;
        memset(&st, 0, sizeof(st));
        st.st_mode = 0020666;
        st.st_nlink = 1;
        if (g_kernel_config.enable_user_mode) {
            if (copy_to_user(a2, &st, sizeof(st)) != 0) return -1;
        } else {
            memcpy((void *)a2, &st, sizeof(st));
        }
        return 0;
    }

    case SYS_UNAME: {
        struct linux_utsname u;
        memset(&u, 0, sizeof(u));
        put_user_str(u.sysname, "pyOS", 65);
        put_user_str(u.nodename, "pyos", 65);
        put_user_str(u.release, "0.2.0", 65);
        put_user_str(u.version, "phase5", 65);
        put_user_str(u.machine, "i386", 65);
        put_user_str(u.domainname, "(none)", 65);
        if (g_kernel_config.enable_user_mode) {
            if (copy_to_user(a1, &u, sizeof(u)) != 0) return -1;
        } else {
            memcpy((void *)a1, &u, sizeof(u));
        }
        return 0;
    }

    case SYS_SCHED_YIELD:
        task_schedule();
        return 0;

    case SYS_NANOSLEEP: {
        u32 ms = 0;
        if (g_kernel_config.enable_user_mode) {
            struct linux_timespec ts;
            if (a1 && copy_from_user(&ts, a1, sizeof(ts)) == 0) {
                ms = (u32)ts.tv_sec * 1000u + (u32)(ts.tv_nsec / 1000000);
            }
        } else {
            /* DSL SysCall.sleep passes milliseconds in a1. */
            ms = a1;
        }
        timer_sleep_ms(ms);
        return 0;
    }

    case SYS_RT_SIGACTION:
    case SYS_RT_SIGPROCMASK:
        return 0;

    case SYS_GETCWD: {
        Task *t = task_current();
        const char *cwd = (t && t->cwd[0]) ? t->cwd : "/";
        u32 len = strlen(cwd) + 1;
        if (a2 < len) return -1;
        if (g_kernel_config.enable_user_mode) {
            if (copy_to_user(a1, cwd, len) != 0) return -1;
        } else {
            memcpy((void *)a1, cwd, len);
        }
        return (i32)a1;
    }

    /* Non-Linux pyOS extensions */
    case PYOS_SYS_MALLOC:
        return (i32)(u32)heap_malloc(a1);
    case PYOS_SYS_FREE:
        heap_free((void *)a1);
        return 0;
    case PYOS_SYS_SPAWN:
        return task_spawn((const char *)a1, a2, a3);

    default:
        debug_log("Unknown syscall number");
        return -1;
    }
}

void syscall_init(void) {
    debug_log("Syscall gate int 0x80 ready (Linux i386 ABI)");
}
