#include "heap.h"
#include "debug.h"

typedef struct Block {
    u32 size;
    u32 free;
    struct Block *next;
} Block;

static u8 *heap_base = 0;
static u32 heap_size = 0;
static Block *free_list = 0;
static u32 used_bytes = 0;

void heap_init(u32 start, u32 size) {
    heap_base = (u8 *)start;
    heap_size = size;
    used_bytes = 0;
    free_list = (Block *)start;
    free_list->size = size - sizeof(Block);
    free_list->free = 1;
    free_list->next = 0;
}

static void split_block(Block *b, u32 size) {
    if (b->size >= size + sizeof(Block) + 16) {
        Block *n = (Block *)((u8 *)b + sizeof(Block) + size);
        n->size = b->size - size - sizeof(Block);
        n->free = 1;
        n->next = b->next;
        b->size = size;
        b->next = n;
    }
}

void *heap_malloc(u32 size) {
    if (size == 0) return NULL;
    size = (size + 3u) & ~3u;
    Block *prev = 0;
    Block *cur = free_list;
    while (cur) {
        if (cur->free && cur->size >= size) {
            split_block(cur, size);
            cur->free = 0;
            used_bytes += cur->size + sizeof(Block);
            return (void *)((u8 *)cur + sizeof(Block));
        }
        prev = cur;
        cur = cur->next;
        (void)prev;
    }
    pyos_panic(
        "@kernel Memory.malloc",
        "Heap exhausted: not enough free memory for this allocation",
        "Increase Kernel(heap_size=...) or free unused buffers"
    );
    return NULL;
}

void heap_free(void *ptr) {
    if (!ptr) return;
    Block *b = (Block *)((u8 *)ptr - sizeof(Block));
    if ((u8 *)b < heap_base || (u8 *)b >= heap_base + heap_size) return;
    if (b->free) return;
    b->free = 1;
    if (used_bytes >= b->size + sizeof(Block))
        used_bytes -= b->size + sizeof(Block);
    /* coalesce forward */
    if (b->next && b->next->free) {
        b->size += sizeof(Block) + b->next->size;
        b->next = b->next->next;
    }
}

void heap_memset(void *dst, int value, u32 size) {
    u8 *p = (u8 *)dst;
    for (u32 i = 0; i < size; i++) p[i] = (u8)value;
}

void heap_memcpy(void *dst, const void *src, u32 size) {
    u8 *d = (u8 *)dst;
    const u8 *s = (const u8 *)src;
    for (u32 i = 0; i < size; i++) d[i] = s[i];
}

void *heap_calloc(u32 count, u32 size) {
    u32 total = count * size;
    void *p = heap_malloc(total);
    if (p) heap_memset(p, 0, total);
    return p;
}

void *heap_realloc(void *ptr, u32 size) {
    if (!ptr) return heap_malloc(size);
    if (size == 0) {
        heap_free(ptr);
        return NULL;
    }
    Block *b = (Block *)((u8 *)ptr - sizeof(Block));
    if (b->size >= size) return ptr;
    void *n = heap_malloc(size);
    if (!n) return NULL;
    heap_memcpy(n, ptr, b->size);
    heap_free(ptr);
    return n;
}

u32 heap_used(void) { return used_bytes; }
u32 heap_free_bytes(void) { return heap_size > used_bytes ? heap_size - used_bytes : 0; }
u32 heap_total(void) { return heap_size; }
