#include "heap.h"
#include "debug.h"

static u32 heap_start = 0;
static u32 heap_end = 0;
static u32 heap_cur = 0;
static u32 heap_size = 0;

void heap_init(u32 start, u32 size) {
    heap_start = start;
    heap_size = size;
    heap_end = start + size;
    heap_cur = start;
}

void *heap_malloc(u32 size) {
    if (size == 0) return NULL;
    /* 4-byte align */
    size = (size + 3) & ~3u;
    if (heap_cur + size > heap_end) {
        pyos_panic(
            "@kernel Memory.malloc",
            "Heap exhausted: not enough free memory for this allocation",
            "Increase Kernel(heap_size=...) or free unused buffers"
        );
        return NULL;
    }
    void *ptr = (void *)heap_cur;
    heap_cur += size;
    return ptr;
}

void heap_free(void *ptr) {
    (void)ptr;
    /* bump allocator: free is a no-op */
}

u32 heap_used(void) {
    return heap_cur - heap_start;
}

u32 heap_free_bytes(void) {
    return heap_end - heap_cur;
}

u32 heap_total(void) {
    return heap_size;
}
