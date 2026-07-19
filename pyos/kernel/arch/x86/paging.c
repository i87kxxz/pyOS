#include "paging.h"
#include "pmm.h"
#include "kernel.h"
#include "debug.h"
#include "task.h"
#include "io.h"
#include "string.h"

static u32 *kernel_pd = 0;
static u32 kernel_pd_phys = 0;
static pyos_bool paging_on = PYOS_FALSE;

static void paging_zero_page(void *page) {
    u8 *p = (u8 *)page;
    for (u32 i = 0; i < PAGE_SIZE; i++) p[i] = 0;
}

static u32 *paging_pd_ptr(u32 pd_phys) {
    return (u32 *)pd_phys;
}

static void paging_invlpg(u32 virt) {
    __asm__ volatile ("invlpg (%0)" : : "r"(virt) : "memory");
}

void paging_map_page(u32 pd_phys, u32 virt, u32 phys, u32 flags) {
    if (!pd_phys) return;
    u32 *pd = paging_pd_ptr(pd_phys);
    u32 pdi = virt >> 22;
    u32 pti = (virt >> 12) & 0x3FFu;
    if (!(pd[pdi] & PAGE_PRESENT)) {
        void *pt_page = pmm_alloc_page();
        if (!pt_page) return;
        paging_zero_page(pt_page);
        /* Page tables for kernel maps stay supervisor-writable. */
        pd[pdi] = ((u32)pt_page & ~PAGE_FLAGS_MASK) | PAGE_PRESENT | PAGE_RW |
                  (flags & PAGE_USER);
    }
    u32 *pt = (u32 *)(pd[pdi] & ~PAGE_FLAGS_MASK);
    pt[pti] = (phys & ~PAGE_FLAGS_MASK) | (flags & PAGE_FLAGS_MASK) | PAGE_PRESENT;
    if (paging_on && pd_phys == kernel_pd_phys) {
        paging_invlpg(virt);
    }
}

void paging_unmap_page(u32 pd_phys, u32 virt) {
    if (!pd_phys) return;
    u32 *pd = paging_pd_ptr(pd_phys);
    u32 pdi = virt >> 22;
    u32 pti = (virt >> 12) & 0x3FFu;
    if (!(pd[pdi] & PAGE_PRESENT)) return;
    u32 *pt = (u32 *)(pd[pdi] & ~PAGE_FLAGS_MASK);
    pt[pti] = 0;
    if (paging_on) {
        u32 cr3;
        __asm__ volatile ("mov %%cr3, %0" : "=r"(cr3));
        if (cr3 == pd_phys) paging_invlpg(virt);
    }
}

pyos_bool paging_is_mapped(u32 pd_phys, u32 virt) {
    if (!pd_phys) return PYOS_FALSE;
    u32 *pd = paging_pd_ptr(pd_phys);
    u32 pdi = virt >> 22;
    u32 pti = (virt >> 12) & 0x3FFu;
    if (!(pd[pdi] & PAGE_PRESENT)) return PYOS_FALSE;
    u32 *pt = (u32 *)(pd[pdi] & ~PAGE_FLAGS_MASK);
    return (pt[pti] & PAGE_PRESENT) ? PYOS_TRUE : PYOS_FALSE;
}

void paging_map_identity(u32 max_addr) {
    if (!kernel_pd_phys) return;
    if (max_addr < PAGE_SIZE) max_addr = PAGE_SIZE;
    max_addr = (max_addr + PAGE_SIZE - 1) & ~(PAGE_SIZE - 1);
    for (u32 addr = 0; addr < max_addr; addr += PAGE_SIZE) {
        paging_map_page(kernel_pd_phys, addr, addr, PAGE_PRESENT | PAGE_RW);
    }
}

u32 paging_create_directory(void) {
    void *page = pmm_alloc_page();
    if (!page) return 0;
    paging_zero_page(page);
    u32 *pd = (u32 *)page;
    /* Share kernel page-table frames so identity maps stay coherent. */
    if (kernel_pd) {
        u32 user_pdi_start = USER_SPACE_BASE >> 22;
        for (u32 i = 0; i < 1024; i++) {
            if (i < user_pdi_start) pd[i] = kernel_pd[i];
            else pd[i] = 0;
        }
    }
    return (u32)page;
}

u32 paging_virt_to_phys(u32 pd_phys, u32 virt) {
    if (!pd_phys) return 0;
    u32 *pd = paging_pd_ptr(pd_phys);
    u32 pdi = virt >> 22;
    u32 pti = (virt >> 12) & 0x3FFu;
    if (!(pd[pdi] & PAGE_PRESENT)) return 0;
    u32 *pt = (u32 *)(pd[pdi] & ~PAGE_FLAGS_MASK);
    if (!(pt[pti] & PAGE_PRESENT)) return 0;
    return (pt[pti] & ~PAGE_FLAGS_MASK) | (virt & PAGE_FLAGS_MASK);
}

static void paging_zero_page_local(void *page) {
    paging_zero_page(page);
}

u32 paging_clone_address_space(u32 src_pd) {
    u32 dst = paging_create_directory();
    if (!dst || !src_pd) return dst;

    u32 *spd = paging_pd_ptr(src_pd);
    u32 user_pdi_start = USER_SPACE_BASE >> 22;
    u32 user_pdi_end = (USER_SPACE_END - 1) >> 22;

    for (u32 pdi = user_pdi_start; pdi <= user_pdi_end; pdi++) {
        if (!(spd[pdi] & PAGE_PRESENT)) continue;
        u32 *spt = (u32 *)(spd[pdi] & ~PAGE_FLAGS_MASK);
        for (u32 pti = 0; pti < 1024; pti++) {
            if (!(spt[pti] & PAGE_PRESENT)) continue;
            u32 virt = (pdi << 22) | (pti << 12);
            u32 src_phys = spt[pti] & ~PAGE_FLAGS_MASK;
            u32 flags = spt[pti] & PAGE_FLAGS_MASK;
            void *frame = pmm_alloc_page();
            if (!frame) return 0;
            /* Identity-mapped phys: copy page contents. */
            memcpy(frame, (void *)src_phys, PAGE_SIZE);
            paging_map_page(dst, virt, (u32)frame, flags);
        }
    }
    return dst;
}

void paging_destroy_user_space(u32 pd_phys) {
    if (!pd_phys || pd_phys == kernel_pd_phys) return;
    u32 *pd = paging_pd_ptr(pd_phys);
    u32 user_pdi_start = USER_SPACE_BASE >> 22;
    u32 user_pdi_end = (USER_SPACE_END - 1) >> 22;

    for (u32 pdi = user_pdi_start; pdi <= user_pdi_end; pdi++) {
        if (!(pd[pdi] & PAGE_PRESENT)) continue;
        u32 *pt = (u32 *)(pd[pdi] & ~PAGE_FLAGS_MASK);
        for (u32 pti = 0; pti < 1024; pti++) {
            if (!(pt[pti] & PAGE_PRESENT)) continue;
            void *frame = (void *)(pt[pti] & ~PAGE_FLAGS_MASK);
            pt[pti] = 0;
            pmm_free_page(frame);
        }
        pd[pdi] = 0;
        pmm_free_page(pt);
    }
}

i32 paging_map_anon_user(u32 pd_phys, u32 virt, u32 size, u32 flags) {
    if (!pd_phys || size == 0) return -1;
    u32 start = virt & ~(PAGE_SIZE - 1);
    u32 end = (virt + size + PAGE_SIZE - 1) & ~(PAGE_SIZE - 1);
    u32 f = flags | PAGE_PRESENT | PAGE_USER;
    for (u32 va = start; va < end; va += PAGE_SIZE) {
        if (paging_is_mapped(pd_phys, va)) continue;
        void *frame = pmm_alloc_page();
        if (!frame) return -1;
        paging_zero_page_local(frame);
        paging_map_page(pd_phys, va, (u32)frame, f);
    }
    return 0;
}

void paging_load_directory(u32 pd_phys) {
    if (!pd_phys) return;
    __asm__ volatile ("mov %0, %%cr3" : : "r"(pd_phys) : "memory");
}

void paging_init(void) {
    void *pd_page = pmm_alloc_page();
    if (!pd_page) {
        debug_log("paging_init: PMM exhausted, paging disabled");
        return;
    }
    paging_zero_page(pd_page);
    kernel_pd = (u32 *)pd_page;
    kernel_pd_phys = (u32)pd_page;

    u32 identity_end = PAGING_IDENTITY_END;
    u32 need = g_kernel_config.heap_start + g_kernel_config.heap_size + 0x200000u;
    if (need > identity_end) identity_end = (need + PAGE_SIZE - 1) & ~(PAGE_SIZE - 1);

    paging_map_identity(identity_end);

    paging_load_directory(kernel_pd_phys);
    __asm__ volatile (
        "mov %%cr0, %%eax\n"
        "or $0x80000000, %%eax\n"
        "mov %%eax, %%cr0\n"
        :
        :
        : "eax", "memory"
    );
    paging_on = PYOS_TRUE;
}

u32 paging_get_directory(void) {
    if (paging_on) {
        u32 cr3;
        __asm__ volatile ("mov %%cr3, %0" : "=r"(cr3));
        return cr3;
    }
    return kernel_pd_phys;
}

pyos_bool paging_enabled(void) {
    return paging_on;
}

void page_fault_handler(u32 err_code, u32 eip) {
    u32 cr2 = 0;
    __asm__ volatile ("mov %%cr2, %0" : "=r"(cr2));

    serial_write_str("[pyOS] PAGE FAULT cr2=");
    serial_write_hex(cr2);
    serial_write_str(" err=");
    serial_write_hex(err_code);
    serial_write_str(" eip=");
    serial_write_hex(eip);
    serial_write_str("\n");

    Task *t = task_current();
    if (t && g_kernel_config.enable_processes && t->state == TASK_RUNNING) {
        serial_write_str("[pyOS] killing task pid=");
        serial_write_dec(t->pid);
        serial_write_str(" (");
        serial_write_str(t->name);
        serial_write_str(")\n");
        t->state = TASK_ZOMBIE;
        /* Never return to the faulting EIP — switch away or halt. */
        task_schedule();
    }

    cli();
    serial_write_str("[pyOS] page fault — halting\n");
    for (;;) hlt();
}
