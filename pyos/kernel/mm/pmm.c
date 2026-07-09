#include "pmm.h"

#define PAGE_SIZE 4096u

static u8 *pmm_base = 0;
static u32 pmm_pages = 0;
static u8 *pmm_bitmap = 0;
static u32 pmm_bitmap_bytes = 0;

void pmm_init(u32 start, u32 size) {
    pmm_base = (u8 *)((start + PAGE_SIZE - 1) & ~(PAGE_SIZE - 1));
    pmm_pages = size / PAGE_SIZE;
    pmm_bitmap_bytes = (pmm_pages + 7) / 8;
    pmm_bitmap = pmm_base;
    for (u32 i = 0; i < pmm_bitmap_bytes; i++) pmm_bitmap[i] = 0;
    /* reserve bitmap pages */
    u32 reserved = (pmm_bitmap_bytes + PAGE_SIZE - 1) / PAGE_SIZE;
    for (u32 i = 0; i < reserved && i < pmm_pages; i++)
        pmm_bitmap[i / 8] |= (u8)(1u << (i % 8));
}

void *pmm_alloc_page(void) {
    for (u32 i = 0; i < pmm_pages; i++) {
        u32 byte = i / 8;
        u8 bit = (u8)(1u << (i % 8));
        if (!(pmm_bitmap[byte] & bit)) {
            pmm_bitmap[byte] |= bit;
            return pmm_base + i * PAGE_SIZE;
        }
    }
    return 0;
}

void pmm_free_page(void *page) {
    if (!page) return;
    u32 off = (u32)((u8 *)page - pmm_base);
    u32 i = off / PAGE_SIZE;
    if (i >= pmm_pages) return;
    pmm_bitmap[i / 8] &= (u8)~(1u << (i % 8));
}
