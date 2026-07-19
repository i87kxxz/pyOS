#ifndef PYOS_PAGING_H
#define PYOS_PAGING_H

#include "types.h"

#define PAGE_SIZE       4096u
#define PAGE_PRESENT    0x1u
#define PAGE_RW         0x2u
#define PAGE_USER       0x4u
#define PAGE_FLAGS_MASK 0xFFFu

/* Identity-map at least this much of physical RAM for the kernel. */
#define PAGING_IDENTITY_END 0x1000000u

void paging_init(void);
u32 paging_get_directory(void);
void paging_map_identity(u32 max_addr);
pyos_bool paging_enabled(void);

/* Map / unmap a single 4KiB page in the given page directory (physical addr). */
void paging_map_page(u32 pd_phys, u32 virt, u32 phys, u32 flags);
void paging_unmap_page(u32 pd_phys, u32 virt);
pyos_bool paging_is_mapped(u32 pd_phys, u32 virt);

/* Allocate a new page directory that shares kernel identity mappings. */
u32 paging_create_directory(void);
void paging_load_directory(u32 pd_phys);

/* User virtual window (must match usercopy.c). */
#define USER_SPACE_BASE 0x08000000u
#define USER_SPACE_END  0xC0000000u

u32 paging_virt_to_phys(u32 pd_phys, u32 virt);
/* Clone address space: share kernel PTs, copy-on-write-style duplicate of user pages. */
u32 paging_clone_address_space(u32 src_pd);
/* Unmap and free frames for user virtual addresses only. */
void paging_destroy_user_space(u32 pd_phys);
/* Map anonymous zeroed user pages [virt, virt+size). */
i32 paging_map_anon_user(u32 pd_phys, u32 virt, u32 size, u32 flags);

/* Page-fault ISR (vector 14) — logs and kills/halts; never returns to fault EIP. */
void page_fault_handler(u32 err_code, u32 eip);

#endif
