#ifndef PYOS_TASK_H
#define PYOS_TASK_H

#include "types.h"

#define TASK_MAX 8

typedef enum {
    TASK_FREE = 0,
    TASK_READY,
    TASK_RUNNING,
    TASK_BLOCKED,
    TASK_ZOMBIE
} TaskState;

typedef struct {
    u32 pid;
    TaskState state;
    u32 esp;
    u32 cr3;
    u32 entry;
    u32 caps;
    char name[16];
} Task;

void task_init(void);
void task_start_init(void);
void task_schedule(void);
i32 task_spawn(const char *name, u32 entry, u32 caps);
void task_exit(i32 code);
u32 task_current_pid(void);
Task *task_current(void);
void task_on_timer(void);

#endif
