#include "task.h"
#include "screen.h"
#include "debug.h"
#include "string.h"
#include "heap.h"
#include "kernel.h"
#include "paging.h"
#include "pmm.h"
#include "io.h"
#include "elf.h"
#include "vfs.h"
#include "gdt.h"

static Task tasks[TASK_MAX];
static u32 current = 0;
static u32 next_pid = 1;
static u32 schedule_counter = 0;
static volatile pyos_bool need_resched = PYOS_FALSE;

extern void task_switch_asm(u32 *old_esp_slot, u32 new_esp, u32 new_cr3);
extern void enter_userspace(u32 eip, u32 esp);

static void task_entry_trampoline(void);
static void fork_child_enter(void);
static void user_init_enter(void);
static i32 task_setup_user_stack(u32 pd, u32 argc, const char **argv_k, ElfLoadInfo *info, u32 *esp_out);
static void poke_u32(u32 pd, u32 vaddr, u32 value);
static void poke_bytes(u32 pd, u32 vaddr, const void *src, u32 len);

static void task_entry_trampoline(void) {
    Task *t = task_current();
    if (t && t->entry) {
        void (*fn)(void) = (void (*)(void))t->entry;
        fn();
    }
    task_exit(0);
}

static void demo_task_a(void) {
    volatile u32 spin = 0;
    for (;;) {
        debug_log("taskA");
        for (u32 i = 0; i < 200000u; i++) spin++;
        task_schedule();
    }
}

static void demo_task_b(void) {
    volatile u32 spin = 0;
    for (;;) {
        debug_log("taskB");
        for (u32 i = 0; i < 200000u; i++) spin++;
        task_schedule();
    }
}

/* Touches an unmapped address once so ISR 14 can be observed in QEMU. */
static void demo_faultor(void) {
    debug_log("faultor");
    volatile u32 *p = (volatile u32 *)0x0A000000u;
    *p = 0xDEAD;
    debug_log("faultor-survived");
}

static void task_clear(Task *t) {
    t->state = TASK_FREE;
    t->pid = 0;
    t->ppid = 0;
    t->exit_code = 0;
    t->esp = 0;
    t->eip = 0;
    t->eflags = 0x202u;
    t->cr3 = 0;
    t->kstack = 0;
    t->entry = 0;
    t->caps = 0xFFFFFFFF;
    t->brk = 0;
    t->mmap_hint = 0x10000000u;
    t->user_eip = 0;
    t->user_esp = 0;
    t->user_eflags = 0x202u;
    t->is_user = PYOS_FALSE;
    t->cwd[0] = '/';
    t->cwd[1] = 0;
    t->name[0] = 0;
    vfs_fd_table_init(t->fds);
}

static void task_setup_stack(Task *t, u32 entry_fn) {
    u8 *stack_mem = (u8 *)pmm_alloc_page();
    if (!stack_mem) {
        stack_mem = (u8 *)heap_malloc(TASK_KSTACK_SIZE);
    }
    if (!stack_mem) {
        t->kstack = 0;
        t->esp = 0;
        return;
    }
    t->kstack = (u32 *)stack_mem;
    u32 *sp = (u32 *)(stack_mem + TASK_KSTACK_SIZE);

    *(--sp) = entry_fn; /* EIP */
    *(--sp) = 0x202u;   /* EFLAGS (IF=1) */
    *(--sp) = 0;        /* EBX */
    *(--sp) = 0;        /* ESI */
    *(--sp) = 0;        /* EDI */
    *(--sp) = 0;        /* EBP */
    t->esp = (u32)sp;
    t->eip = entry_fn;
    t->eflags = 0x202u;
}

void task_init(void) {
    for (int i = 0; i < TASK_MAX; i++) task_clear(&tasks[i]);
    current = 0;
    next_pid = 1;
    schedule_counter = 0;
    need_resched = PYOS_FALSE;
}

Task *task_current(void) {
    if (tasks[current].state == TASK_FREE) return 0;
    return &tasks[current];
}

u32 task_current_pid(void) {
    Task *t = task_current();
    return t ? t->pid : 0;
}

void task_save_user_frame(u32 eip, u32 cs, u32 eflags, u32 user_esp, u32 user_ss) {
    (void)cs;
    (void)user_ss;
    Task *t = task_current();
    if (!t) return;
    t->user_eip = eip;
    t->user_esp = user_esp;
    t->user_eflags = eflags;
    t->is_user = PYOS_TRUE;
}

i32 task_spawn(const char *name, u32 entry, u32 caps) {
    for (int i = 0; i < TASK_MAX; i++) {
        if (tasks[i].state == TASK_FREE) {
            task_clear(&tasks[i]);
            tasks[i].pid = next_pid++;
            tasks[i].ppid = task_current_pid();
            tasks[i].state = TASK_READY;
            tasks[i].entry = entry;
            tasks[i].caps = caps ? caps : 0xFFFFFFFF;
            tasks[i].cr3 = paging_enabled() ? paging_get_directory() : 0;
            strncpy(tasks[i].name, name ? name : "task", 15);
            tasks[i].name[15] = 0;
            task_setup_stack(&tasks[i], (u32)task_entry_trampoline);
            if (!tasks[i].esp) {
                tasks[i].state = TASK_FREE;
                return -1;
            }
            return (i32)tasks[i].pid;
        }
    }
    return -1;
}

static void fork_child_enter(void) {
    Task *t = task_current();
    if (!t) {
        task_exit(0);
        return;
    }
    if (t->kstack) {
        tss_set_kernel_stack((u32)t->kstack + TASK_KSTACK_SIZE);
    }
    /* Child returns 0 from fork via enter_userspace; EAX cleared before iret. */
    u32 eip = t->user_eip;
    u32 esp = t->user_esp;
    __asm__ volatile (
        "movw $0x23, %%ax\n"
        "movw %%ax, %%ds\n"
        "movw %%ax, %%es\n"
        "movw %%ax, %%fs\n"
        "movw %%ax, %%gs\n"
        "pushl $0x23\n"
        "pushl %1\n"
        "pushfl\n"
        "orl $0x200, (%%esp)\n"
        "pushl $0x1B\n"
        "pushl %0\n"
        "xorl %%eax, %%eax\n"
        "iret\n"
        :
        : "r"(eip), "r"(esp)
        : "eax", "memory"
    );
    task_exit(0);
}

i32 task_fork(void) {
    Task *parent = task_current();
    if (!parent) return -1;

    int slot = -1;
    for (int i = 0; i < TASK_MAX; i++) {
        if (tasks[i].state == TASK_FREE) {
            slot = i;
            break;
        }
    }
    if (slot < 0) return -1;

    Task *child = &tasks[slot];
    task_clear(child);
    child->pid = next_pid++;
    child->ppid = parent->pid;
    child->state = TASK_READY;
    child->caps = parent->caps;
    child->brk = parent->brk;
    child->mmap_hint = parent->mmap_hint;
    child->user_eip = parent->user_eip;
    child->user_esp = parent->user_esp;
    child->user_eflags = parent->user_eflags;
    child->is_user = parent->is_user;
    strncpy(child->cwd, parent->cwd, TASK_CWD_LEN - 1);
    strncpy(child->name, parent->name, 15);
    child->name[15] = 0;
    for (int i = 0; i < VFS_MAX_FDS; i++) child->fds[i] = parent->fds[i];

    if (paging_enabled() && parent->cr3) {
        child->cr3 = paging_clone_address_space(parent->cr3);
        if (!child->cr3) {
            task_clear(child);
            return -1;
        }
    } else {
        child->cr3 = parent->cr3;
    }

    if (parent->is_user && parent->user_eip) {
        task_setup_stack(child, (u32)fork_child_enter);
    } else {
        child->entry = parent->entry;
        task_setup_stack(child, (u32)task_entry_trampoline);
    }
    if (!child->esp) {
        if (child->cr3 && child->cr3 != parent->cr3) {
            paging_destroy_user_space(child->cr3);
            pmm_free_page((void *)child->cr3);
        }
        task_clear(child);
        return -1;
    }
    return (i32)child->pid;
}

/* Build argc/argv/envp/auxv on the user stack. argv_k may be NULL. */
static void poke_u32(u32 pd, u32 vaddr, u32 value) {
    u32 page = vaddr & ~(PAGE_SIZE - 1);
    u32 phys = paging_virt_to_phys(pd, page);
    if (!phys) return;
    *(u32 *)(phys + (vaddr - page)) = value;
}

static void poke_bytes(u32 pd, u32 vaddr, const void *src, u32 len) {
    const u8 *s = (const u8 *)src;
    for (u32 i = 0; i < len; i++) {
        u32 va = vaddr + i;
        u32 page = va & ~(PAGE_SIZE - 1);
        u32 phys = paging_virt_to_phys(pd, page);
        if (!phys) return;
        ((u8 *)phys)[va - page] = s[i];
    }
}

static i32 task_setup_user_stack(u32 pd, u32 argc, const char **argv_k, ElfLoadInfo *info, u32 *esp_out) {
    u32 stack_bytes = TASK_USER_STACK_PAGES * PAGE_SIZE;
    u32 stack_base = TASK_USER_STACK_TOP - stack_bytes;
    if (paging_map_anon_user(pd, stack_base, stack_bytes, PAGE_PRESENT | PAGE_RW | PAGE_USER) != 0) {
        return -1;
    }

    u32 sp = TASK_USER_STACK_TOP;
    u32 argv_ptrs[8];
    u32 narg = argc;
    if (narg > 7) narg = 7;
    if (!argv_k) narg = 0;

    for (u32 i = 0; i < narg; i++) {
        const char *s = argv_k[i] ? argv_k[i] : "";
        u32 len = strlen(s) + 1;
        sp -= len;
        poke_bytes(pd, sp, s, len);
        argv_ptrs[i] = sp;
    }

    sp &= ~0xFu;

    /* auxv: AT_PAGESZ, then AT_NULL */
    sp -= 4; poke_u32(pd, sp, 0);      /* AT_NULL value */
    sp -= 4; poke_u32(pd, sp, 0);      /* AT_NULL type */
    sp -= 4; poke_u32(pd, sp, 4096);   /* AT_PAGESZ value */
    sp -= 4; poke_u32(pd, sp, 6);      /* AT_PAGESZ */

    /* envp NULL */
    sp -= 4; poke_u32(pd, sp, 0);

    /* argv pointers + NULL */
    sp -= 4; poke_u32(pd, sp, 0);
    for (i32 i = (i32)narg - 1; i >= 0; i--) {
        sp -= 4;
        poke_u32(pd, sp, argv_ptrs[i]);
    }

    sp -= 4;
    poke_u32(pd, sp, narg);

    (void)info;
    *esp_out = sp;
    return 0;
}

static void user_init_enter(void) {
    Task *t = task_current();
    if (!t) {
        task_exit(1);
        return;
    }
    if (t->kstack) {
        tss_set_kernel_stack((u32)t->kstack + TASK_KSTACK_SIZE);
    }
    if (t->cr3) paging_load_directory(t->cr3);
    debug_log("enter userspace ELF");
    enter_userspace(t->user_eip, t->user_esp);
    task_exit(1);
}

i32 task_execve(const char *path, u32 argv_user, u32 envp_user) {
    (void)argv_user;
    (void)envp_user;
    Task *t = task_current();
    if (!t || !path) return -1;

    const u8 *image = 0;
    u32 size = 0;
    if (vfs_load_file(path, &image, &size) != 0 || !image || size == 0) return -1;

    if (!paging_enabled()) return -1;

    u32 new_pd = paging_create_directory();
    if (!new_pd) return -1;

    ElfLoadInfo info;
    if (elf_load(image, size, new_pd, &info) != 0) {
        paging_destroy_user_space(new_pd);
        pmm_free_page((void *)new_pd);
        return -1;
    }

    const char *argv0 = path;
    const char *argv_k[2] = { argv0, 0 };
    u32 user_esp = 0;
    if (task_setup_user_stack(new_pd, 1, argv_k, &info, &user_esp) != 0) {
        paging_destroy_user_space(new_pd);
        pmm_free_page((void *)new_pd);
        return -1;
    }

    /* Replace address space. */
    u32 old_pd = t->cr3;
    if (old_pd && old_pd != paging_get_directory() && old_pd != new_pd) {
        /* Only destroy if it was a private user PD (not kernel). */
        u32 kpd = 0;
        /* kernel pd is shared; never free it. Heuristic: if old had user pages, destroy them. */
        paging_destroy_user_space(old_pd);
        /* Do not free the PD page if it is the live kernel directory. */
        {
            u32 cr3_now = paging_get_directory();
            if (old_pd != cr3_now) {
                /* Keep PD frame if still referenced — for simplicity free only user PTs. */
            }
        }
        (void)kpd;
    }

    t->cr3 = new_pd;
    t->brk = info.brk;
    t->mmap_hint = (info.brk + 0x100000u) & ~(PAGE_SIZE - 1);
    if (t->mmap_hint < 0x10000000u) t->mmap_hint = 0x10000000u;
    t->user_eip = info.entry;
    t->user_esp = user_esp;
    t->user_eflags = 0x202u;
    t->is_user = PYOS_TRUE;
    t->entry = (u32)user_init_enter;
    strncpy(t->name, path, 15);
    t->name[15] = 0;

    paging_load_directory(new_pd);
    if (t->kstack) {
        tss_set_kernel_stack((u32)t->kstack + TASK_KSTACK_SIZE);
    }

    /* Jump to user — does not return. */
    enter_userspace(t->user_eip, t->user_esp);
    return -1;
}

i32 task_try_exec_init(const char *path) {
    if (!path || !g_kernel_config.enable_user_mode) return -1;
    if (!paging_enabled()) return -1;

    const u8 *image = 0;
    u32 size = 0;
    if (vfs_load_file(path, &image, &size) != 0 || !image || size == 0) return -1;

    /* Spawn a dedicated user process that loads the ELF. */
    for (int i = 0; i < TASK_MAX; i++) {
        if (tasks[i].state != TASK_FREE) continue;
        task_clear(&tasks[i]);
        tasks[i].pid = next_pid++;
        tasks[i].ppid = task_current_pid();
        tasks[i].state = TASK_READY;
        tasks[i].caps = 0xFFFFFFFF;
        strncpy(tasks[i].name, path, 15);
        tasks[i].name[15] = 0;

        tasks[i].entry = 0;
        tasks[i].user_eip = 0;
        task_setup_stack(&tasks[i], (u32)user_init_enter);

        u32 pd = paging_create_directory();
        if (!pd) {
            task_clear(&tasks[i]);
            return -1;
        }
        ElfLoadInfo info;
        if (elf_load(image, size, pd, &info) != 0) {
            paging_destroy_user_space(pd);
            pmm_free_page((void *)pd);
            task_clear(&tasks[i]);
            return -1;
        }
        const char *argv_k[2] = { path, 0 };
        u32 user_esp = 0;
        if (task_setup_user_stack(pd, 1, argv_k, &info, &user_esp) != 0) {
            paging_destroy_user_space(pd);
            pmm_free_page((void *)pd);
            task_clear(&tasks[i]);
            return -1;
        }
        tasks[i].cr3 = pd;
        tasks[i].brk = info.brk;
        tasks[i].mmap_hint = 0x10000000u;
        tasks[i].user_eip = info.entry;
        tasks[i].user_esp = user_esp;
        tasks[i].is_user = PYOS_TRUE;
        if (!tasks[i].esp) {
            task_clear(&tasks[i]);
            return -1;
        }
        debug_log("init ELF scheduled");
        return (i32)tasks[i].pid;
    }
    return -1;
}

i32 task_waitpid(i32 pid, i32 *status_out, i32 options) {
    (void)options;
    for (;;) {
        pyos_bool found = PYOS_FALSE;
        for (int i = 0; i < TASK_MAX; i++) {
            if (tasks[i].state == TASK_FREE) continue;
            if (tasks[i].ppid != task_current_pid()) continue;
            if (pid > 0 && (i32)tasks[i].pid != pid) continue;
            found = PYOS_TRUE;
            if (tasks[i].state == TASK_ZOMBIE) {
                i32 reaped = (i32)tasks[i].pid;
                if (status_out) *status_out = tasks[i].exit_code;
                if (tasks[i].cr3) {
                    paging_destroy_user_space(tasks[i].cr3);
                }
                task_clear(&tasks[i]);
                return reaped;
            }
        }
        if (!found) return -1;
        task_schedule();
    }
}

void task_exit(i32 code) {
    if (tasks[current].state != TASK_FREE) {
        tasks[current].exit_code = code;
        tasks[current].state = TASK_ZOMBIE;
        serial_write_str("[pyOS] task exit pid=");
        serial_write_dec(tasks[current].pid);
        serial_write_str("\n");
    }
    task_schedule();
    cli();
    for (;;) hlt();
}

static i32 task_pick_next(void) {
    u32 start = current;
    for (int n = 0; n < TASK_MAX; n++) {
        u32 idx = (start + 1 + (u32)n) % TASK_MAX;
        if (tasks[idx].state == TASK_READY || tasks[idx].state == TASK_RUNNING) {
            return (i32)idx;
        }
    }
    return -1;
}

void task_schedule(void) {
    if (!g_kernel_config.enable_processes) return;

    cli();
    i32 next = task_pick_next();
    if (next < 0) {
        sti();
        return;
    }
    if ((u32)next == current) {
        if (tasks[current].state == TASK_READY)
            tasks[current].state = TASK_RUNNING;
        sti();
        return;
    }

    Task *old = &tasks[current];
    Task *neu = &tasks[next];

    if (old->state == TASK_RUNNING)
        old->state = TASK_READY;
    neu->state = TASK_RUNNING;

    if (neu->kstack) {
        tss_set_kernel_stack((u32)neu->kstack + TASK_KSTACK_SIZE);
    }

    u32 *old_slot = &old->esp;
    u32 new_esp = neu->esp;
    u32 new_cr3 = neu->cr3 ? neu->cr3 : (old->cr3 ? old->cr3 : 0);

    current = (u32)next;
    task_switch_asm(old_slot, new_esp, new_cr3);
    sti();
}

void task_on_timer(void) {
    if (!g_kernel_config.enable_processes) return;
    schedule_counter++;
    if (schedule_counter >= 5) {
        schedule_counter = 0;
        need_resched = PYOS_TRUE;
    }
}

pyos_bool task_consume_reschedule(void) {
    if (!need_resched) return PYOS_FALSE;
    need_resched = PYOS_FALSE;
    return PYOS_TRUE;
}

void task_start_init(void) {
    u32 cr3 = paging_enabled() ? paging_get_directory() : 0;

    tasks[0].pid = next_pid++;
    tasks[0].ppid = 0;
    tasks[0].state = TASK_RUNNING;
    tasks[0].esp = 0;
    tasks[0].eip = 0;
    tasks[0].eflags = 0x202u;
    tasks[0].cr3 = cr3;
    tasks[0].kstack = 0;
    tasks[0].entry = 0;
    tasks[0].caps = 0xFFFFFFFF;
    tasks[0].is_user = PYOS_FALSE;
    tasks[0].cwd[0] = '/';
    tasks[0].cwd[1] = 0;
    strncpy(tasks[0].name, "idle", 15);
    tasks[0].name[15] = 0;
    current = 0;

    if (g_kernel_config.enable_user_mode) {
        /* Phase 5: prefer disk userland /init, then BusyBox, then seed "hi". */
        VfsPathInfo info;
        if (vfs_resolve("/init", &info) == 0 && info.found) {
            if (task_try_exec_init("/init") >= 0) {
                debug_log("Process table ready (userland /init)");
                screen_print_at("tasks: idle+init", 22, 0, 0x0A);
                return;
            }
            debug_log("exec /init failed");
        }
        if (vfs_resolve("/bin/busybox", &info) == 0 && info.found) {
            if (task_try_exec_init("/bin/busybox") >= 0) {
                debug_log("Process table ready (BusyBox)");
                screen_print_at("tasks: idle+bb", 22, 0, 0x0A);
                return;
            }
            debug_log("exec /bin/busybox failed");
        }
        if (vfs_lookup("hi") >= 0) {
            if (task_try_exec_init("hi") >= 0) {
                debug_log("Process table ready (user ELF hi)");
                screen_print_at("tasks: idle+hi", 22, 0, 0x0A);
                return;
            }
            debug_log("exec hi failed; falling back to demos");
        }
    }

    task_spawn("taskA", (u32)demo_task_a, 0xFFFFFFFF);
    task_spawn("taskB", (u32)demo_task_b, 0xFFFFFFFF);
    if (paging_enabled()) {
        task_spawn("faultor", (u32)demo_faultor, 0xFFFFFFFF);
    }

    debug_log("Process table ready (context switch on IRQ0/YIELD)");
    screen_print_at("tasks: idle+A+B", 22, 0, 0x0A);
}
