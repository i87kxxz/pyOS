#ifndef PYOS_HEAP_H
#define PYOS_HEAP_H

#include "types.h"

void heap_init(u32 start, u32 size);
void *heap_malloc(u32 size);
void heap_free(void *ptr);
u32 heap_used(void);
u32 heap_free_bytes(void);
u32 heap_total(void);

#endif
