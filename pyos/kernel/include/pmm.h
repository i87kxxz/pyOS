#ifndef PYOS_PMM_H
#define PYOS_PMM_H

#include "types.h"

#define PMM_PAGE_SIZE 4096u

void pmm_init(u32 start, u32 size);
void *pmm_alloc_page(void);
void pmm_free_page(void *page);
void *pmm_alloc_pages(u32 count);
void pmm_free_pages(void *page, u32 count);
u32 pmm_total_pages(void);
u32 pmm_used_pages(void);
u32 pmm_free_count(void);

#endif
