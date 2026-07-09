#include "paging.h"
#include "types.h"

#define PAGE_PRESENT 0x1
#define PAGE_RW      0x2

/* Place page tables in low memory above classic EBDA, below kernel load */
#define PD_ADDR  0x70000
#define PT_ADDR  0x71000

static pyos_bool paging_on = PYOS_FALSE;

void paging_map_identity(u32 max_addr) {
    (void)max_addr;
    u32 *page_directory = (u32 *)PD_ADDR;
    u32 *first_table = (u32 *)PT_ADDR;
    for (int i = 0; i < 1024; i++) {
        page_directory[i] = 0;
        first_table[i] = (u32)(i * 0x1000) | PAGE_PRESENT | PAGE_RW;
    }
    page_directory[0] = (u32)first_table | PAGE_PRESENT | PAGE_RW;
}

void paging_init(void) {
    paging_map_identity(0x400000);
    u32 pd = PD_ADDR;
    __asm__ volatile (
        "mov %0, %%cr3\n"
        "mov %%cr0, %%eax\n"
        "or $0x80000000, %%eax\n"
        "mov %%eax, %%cr0\n"
        :
        : "r"(pd)
        : "eax", "memory"
    );
    paging_on = PYOS_TRUE;
}

u32 paging_get_directory(void) {
    return PD_ADDR;
}

pyos_bool paging_enabled(void) {
    return paging_on;
}
