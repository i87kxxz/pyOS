#include "task.h"
#include "screen.h"
#include "debug.h"
#include "string.h"
#include "heap.h"
#include "kernel.h"

static Task tasks[TASK_MAX];
static u32 current = 0;
static u32 next_pid = 1;
static u32 schedule_counter = 0;

void task_init(void) {
    for (int i = 0; i < TASK_MAX; i++) {
        tasks[i].state = TASK_FREE;
        tasks[i].pid = 0;
        tasks[i].name[0] = 0;
        tasks[i].caps = 0xFFFFFFFF;
    }
    current = 0;
    next_pid = 1;
}

Task *task_current(void) {
    if (tasks[current].state == TASK_FREE) return 0;
    return &tasks[current];
}

u32 task_current_pid(void) {
    Task *t = task_current();
    return t ? t->pid : 0;
}

i32 task_spawn(const char *name, u32 entry, u32 caps) {
    for (int i = 0; i < TASK_MAX; i++) {
        if (tasks[i].state == TASK_FREE) {
            tasks[i].pid = next_pid++;
            tasks[i].state = TASK_READY;
            tasks[i].entry = entry;
            tasks[i].esp = 0;
            tasks[i].cr3 = 0;
            tasks[i].caps = caps ? caps : 0xFFFFFFFF;
            strncpy(tasks[i].name, name ? name : "task", 15);
            tasks[i].name[15] = 0;
            return (i32)tasks[i].pid;
        }
    }
    return -1;
}

void task_exit(i32 code) {
    (void)code;
    if (tasks[current].state != TASK_FREE) {
        tasks[current].state = TASK_ZOMBIE;
    }
    task_schedule();
}

void task_schedule(void) {
    if (!g_kernel_config.enable_processes) return;
    u32 start = current;
    for (int n = 0; n < TASK_MAX; n++) {
        current = (current + 1) % TASK_MAX;
        if (tasks[current].state == TASK_READY || tasks[current].state == TASK_RUNNING) {
            tasks[current].state = TASK_RUNNING;
            return;
        }
        if (current == start) break;
    }
}

void task_on_timer(void) {
    schedule_counter++;
    if (schedule_counter >= 10) {
        schedule_counter = 0;
        if (tasks[current].state == TASK_RUNNING)
            tasks[current].state = TASK_READY;
        task_schedule();
    }
}

void task_start_init(void) {
    /* Create idle + demo worker tasks */
    task_spawn("idle", 0, 0xFFFFFFFF);
    task_spawn("worker", 0, 0xFFFFFFFF);
    current = 0;
    if (tasks[0].state == TASK_READY) tasks[0].state = TASK_RUNNING;
    debug_log("Process table ready (round-robin on IRQ0)");
    screen_print_at("tasks: idle+worker", 22, 0, 0x0A);
}
