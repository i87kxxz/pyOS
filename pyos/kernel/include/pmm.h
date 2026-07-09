#ifndef PYOS_PMM_H
#define PYOS_PMM_H

#include "types.h"

void pmm_init(u32 start, u32 size);
void *pmm_alloc_page(void);
void pmm_free_page(void *page);

#endif
