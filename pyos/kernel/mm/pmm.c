#include "pmm.h"

static u8 *pmm_base = 0;
static u32 pmm_pages = 0;
static u8 *pmm_bitmap = 0;
static u32 pmm_bitmap_bytes = 0;
static u32 pmm_used = 0;

static void pmm_set(u32 i) {
    pmm_bitmap[i / 8] |= (u8)(1u << (i % 8));
}

static void pmm_clear(u32 i) {
    pmm_bitmap[i / 8] &= (u8)~(1u << (i % 8));
}

static pyos_bool pmm_test(u32 i) {
    return (pmm_bitmap[i / 8] & (u8)(1u << (i % 8))) != 0;
}

void pmm_init(u32 start, u32 size) {
    pmm_base = (u8 *)((start + PMM_PAGE_SIZE - 1) & ~(PMM_PAGE_SIZE - 1));
    pmm_pages = size / PMM_PAGE_SIZE;
    pmm_bitmap_bytes = (pmm_pages + 7) / 8;
    pmm_bitmap = pmm_base;
    pmm_used = 0;
    for (u32 i = 0; i < pmm_bitmap_bytes; i++) pmm_bitmap[i] = 0;
    /* reserve bitmap pages */
    u32 reserved = (pmm_bitmap_bytes + PMM_PAGE_SIZE - 1) / PMM_PAGE_SIZE;
    for (u32 i = 0; i < reserved && i < pmm_pages; i++) {
        pmm_set(i);
        pmm_used++;
    }
}

void *pmm_alloc_page(void) {
    for (u32 i = 0; i < pmm_pages; i++) {
        if (!pmm_test(i)) {
            pmm_set(i);
            pmm_used++;
            u8 *page = pmm_base + i * PMM_PAGE_SIZE;
            for (u32 j = 0; j < PMM_PAGE_SIZE; j++) page[j] = 0;
            return page;
        }
    }
    return 0;
}

void *pmm_alloc_pages(u32 count) {
    if (count == 0) return 0;
    if (count == 1) return pmm_alloc_page();
    for (u32 i = 0; i + count <= pmm_pages; i++) {
        u32 j;
        for (j = 0; j < count; j++) {
            if (pmm_test(i + j)) break;
        }
        if (j == count) {
            for (j = 0; j < count; j++) {
                pmm_set(i + j);
                pmm_used++;
            }
            u8 *page = pmm_base + i * PMM_PAGE_SIZE;
            for (u32 k = 0; k < count * PMM_PAGE_SIZE; k++) page[k] = 0;
            return page;
        }
    }
    return 0;
}

void pmm_free_page(void *page) {
    if (!page || !pmm_base) return;
    u32 off = (u32)((u8 *)page - pmm_base);
    if (off % PMM_PAGE_SIZE) return;
    u32 i = off / PMM_PAGE_SIZE;
    if (i >= pmm_pages) return;
    if (!pmm_test(i)) return;
    pmm_clear(i);
    if (pmm_used) pmm_used--;
}

void pmm_free_pages(void *page, u32 count) {
    if (!page || count == 0) return;
    u8 *p = (u8 *)page;
    for (u32 i = 0; i < count; i++) {
        pmm_free_page(p + i * PMM_PAGE_SIZE);
    }
}

u32 pmm_total_pages(void) { return pmm_pages; }
u32 pmm_used_pages(void) { return pmm_used; }
u32 pmm_free_count(void) {
    return pmm_pages > pmm_used ? pmm_pages - pmm_used : 0;
}
