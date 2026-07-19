#ifndef PYOS_HEAP_H
#define PYOS_HEAP_H

#include "types.h"

void heap_init(u32 start, u32 size);
void *heap_malloc(u32 size);
void heap_free(void *ptr);
void *heap_calloc(u32 count, u32 size);
void *heap_realloc(void *ptr, u32 size);
void *heap_aligned_alloc(u32 alignment, u32 size);
void heap_memset(void *dst, int value, u32 size);
void heap_memcpy(void *dst, const void *src, u32 size);
u32 heap_used(void);
u32 heap_free_bytes(void);
u32 heap_total(void);

#endif
