#ifndef PYOS_SYSCALL_H
#define PYOS_SYSCALL_H

#include "types.h"

/*
 * Linux i386 syscall numbers (syscall_32.tbl).
 * Default dispatch uses these. Legacy pyOS-only calls live under PYOS_SYS_*.
 */
#define SYS_EXIT            1
#define SYS_FORK            2
#define SYS_READ            3
#define SYS_WRITE           4
#define SYS_OPEN            5
#define SYS_CLOSE           6
#define SYS_WAITPID         7
#define SYS_EXECVE          11
#define SYS_CHDIR           12
#define SYS_TIME            13
#define SYS_GETPID          20
#define SYS_GETUID          24
#define SYS_DUP             41
#define SYS_PIPE            42
#define SYS_BRK             45
#define SYS_GETGID          47
#define SYS_IOCTL           54
#define SYS_FCNTL           55
#define SYS_DUP2            63
#define SYS_SELECT          82
#define SYS_MMAP            90
#define SYS_MUNMAP          91
#define SYS_SOCKETCALL      102
#define SYS_STAT            106
#define SYS_LSTAT           107
#define SYS_FSTAT           108
#define SYS_UNAME           109
#define SYS_WAIT4           114
#define SYS_MPROTECT        125
#define SYS_SCHED_YIELD     158
#define SYS_NANOSLEEP       162
#define SYS_POLL            168
#define SYS_RT_SIGACTION    174
#define SYS_RT_SIGPROCMASK  175
#define SYS_GETCWD          183
#define SYS_MMAP2           192
#define SYS_GETDENTS        141
#define SYS_GETDENTS64      220
#define SYS_SET_THREAD_AREA 243
#define SYS_EXIT_GROUP      252
#define SYS_ACCESS          33
#define SYS_GETEUID         49
#define SYS_GETEGID         50
#define SYS_GETPPID         64
#define SYS_UGETRLIMIT      191
#define SYS_OPENAT          295
#define SYS_FACCESSAT       307

/* DSL / legacy aliases mapped onto Linux numbers where possible. */
#define SYS_YIELD  SYS_SCHED_YIELD
#define SYS_SLEEP  SYS_NANOSLEEP

/* Non-Linux pyOS extensions (not in the default Linux table path). */
#define PYOS_SYS_MALLOC  0x70000001u
#define PYOS_SYS_FREE    0x70000002u
#define PYOS_SYS_SPAWN   0x70000003u

void syscall_init(void);

/* Linux i386-style: up to 6 args; return value goes back to userspace in EAX. */
i32 syscall_dispatch(u32 num, u32 a1, u32 a2, u32 a3, u32 a4, u32 a5, u32 a6);

/* Called from isr stub; must return the syscall result in EAX. */
i32 syscall_handler_c(u32 num, u32 a1, u32 a2, u32 a3, u32 a4, u32 a5, u32 a6);

#endif
