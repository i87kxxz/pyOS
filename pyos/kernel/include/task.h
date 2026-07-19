#ifndef PYOS_TASK_H
#define PYOS_TASK_H

#include "types.h"
#include "vfs.h"

#define TASK_MAX 8
#define TASK_KSTACK_SIZE 4096u
#define TASK_USER_STACK_TOP 0xBFFFF000u
#define TASK_USER_STACK_PAGES 4u
#define TASK_CWD_LEN 64

typedef enum {
    TASK_FREE = 0,
    TASK_READY,
    TASK_RUNNING,
    TASK_BLOCKED,
    TASK_ZOMBIE
} TaskState;

typedef struct {
    u32 pid;
    u32 ppid;
    TaskState state;
    i32 exit_code;
    u32 esp;       /* kernel stack pointer for switch */
    u32 eip;       /* entry / last known EIP */
    u32 eflags;
    u32 cr3;       /* page directory physical address */
    u32 *kstack;   /* base of kernel stack page (NULL = boot/idle stack) */
    u32 entry;     /* entry function address (kernel threads) */
    u32 caps;
    u32 brk;       /* current program break */
    u32 mmap_hint; /* next anonymous mmap address */
    u32 user_eip;
    u32 user_esp;
    u32 user_eflags;
    pyos_bool is_user;
    char cwd[TASK_CWD_LEN];
    char name[16];
    VfsFd fds[VFS_MAX_FDS];
} Task;

void task_init(void);
void task_start_init(void);
void task_schedule(void);
i32 task_spawn(const char *name, u32 entry, u32 caps);
void task_exit(i32 code);
u32 task_current_pid(void);
Task *task_current(void);
void task_on_timer(void);
pyos_bool task_consume_reschedule(void);

i32 task_fork(void);
i32 task_execve(const char *path, u32 argv_user, u32 envp_user);
i32 task_waitpid(i32 pid, i32 *status_out, i32 options);
void task_save_user_frame(u32 eip, u32 cs, u32 eflags, u32 user_esp, u32 user_ss);
i32 task_try_exec_init(const char *path);

/* ASM: save callee-saved regs + eflags to *old_esp_slot, load new_esp/cr3. */
void task_switch_asm(u32 *old_esp_slot, u32 new_esp, u32 new_cr3);
/* ASM: iret into ring3 at (eip, esp). Does not return. */
void enter_userspace(u32 eip, u32 esp);

#endif
