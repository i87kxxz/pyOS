#include "elf.h"
#include "paging.h"
#include "pmm.h"
#include "string.h"
#include "debug.h"

/* Flat binary loader: entry = load address (image already in memory). */
i32 elf_load_flat(const u8 *image, u32 size, u32 *entry_out) {
    if (!image || size < 4 || !entry_out) return -1;
    u32 entry = (u32)image[0] | ((u32)image[1] << 8) | ((u32)image[2] << 16) | ((u32)image[3] << 24);
    if (entry == 0) entry = (u32)image;
    *entry_out = entry;
    return 0;
}

i32 elf_validate(const u8 *image, u32 size) {
    if (!image || size < sizeof(Elf32Ehdr)) return -1;
    const Elf32Ehdr *eh = (const Elf32Ehdr *)image;
    if (eh->magic != ELF_MAGIC) return -1;
    if (eh->cls != ELF_CLASS32) return -1;
    if (eh->data != ELF_DATA_LSB) return -1;
    if (eh->machine != ELF_EM_386) return -1;
    if (eh->type != ELF_ET_EXEC && eh->type != ELF_ET_DYN) return -1;
    if (eh->phoff == 0 || eh->phentsize < sizeof(Elf32Phdr) || eh->phnum == 0) return -1;
    u32 ph_end = eh->phoff + (u32)eh->phnum * (u32)eh->phentsize;
    if (ph_end > size || ph_end < eh->phoff) return -1;
    return 0;
}

static void elf_zero_page(void *page) {
    memset(page, 0, PAGE_SIZE);
}

static i32 elf_map_segment(u32 pd_phys, u32 vaddr, u32 memsz, u32 filesz,
                           const u8 *file_base, u32 file_off, u32 file_total,
                           u32 flags) {
    if (memsz == 0) return 0;
    u32 page_flags = PAGE_PRESENT | PAGE_USER;
    if (flags & ELF_PF_W) page_flags |= PAGE_RW;

    u32 start = vaddr & ~(PAGE_SIZE - 1);
    u32 end = (vaddr + memsz + PAGE_SIZE - 1) & ~(PAGE_SIZE - 1);

    for (u32 va = start; va < end; va += PAGE_SIZE) {
        void *frame = pmm_alloc_page();
        if (!frame) return -1;
        elf_zero_page(frame);

        /* Copy file bytes that overlap this page. */
        u32 seg_off = (va < vaddr) ? 0 : (va - vaddr);
        if (seg_off < filesz) {
            u32 page_dst_off = (va < vaddr) ? (vaddr - va) : 0;
            u32 copy_src = file_off + seg_off;
            u32 copy_len = filesz - seg_off;
            if (copy_len > PAGE_SIZE - page_dst_off) copy_len = PAGE_SIZE - page_dst_off;
            if (copy_src + copy_len > file_total) {
                if (copy_src >= file_total) copy_len = 0;
                else copy_len = file_total - copy_src;
            }
            if (copy_len) {
                memcpy((u8 *)frame + page_dst_off, file_base + copy_src, copy_len);
            }
        }

        paging_map_page(pd_phys, va, (u32)frame, page_flags);
    }
    return 0;
}

i32 elf_load(const u8 *image, u32 size, u32 pd_phys, ElfLoadInfo *info) {
    if (elf_validate(image, size) != 0 || !pd_phys || !info) return -1;
    const Elf32Ehdr *eh = (const Elf32Ehdr *)image;

    u32 load_base = 0xFFFFFFFFu;
    u32 load_end = 0;

    for (u16 i = 0; i < eh->phnum; i++) {
        const Elf32Phdr *ph = (const Elf32Phdr *)(image + eh->phoff + (u32)i * eh->phentsize);
        if (ph->type != ELF_PT_LOAD) continue;
        if (ph->offset + ph->filesz < ph->offset || ph->offset + ph->filesz > size) return -1;
        if (ph->vaddr < load_base) load_base = ph->vaddr;
        u32 end = ph->vaddr + ph->memsz;
        if (end > load_end) load_end = end;

        if (elf_map_segment(pd_phys, ph->vaddr, ph->memsz, ph->filesz,
                            image, ph->offset, size, ph->flags) != 0) {
            return -1;
        }
    }

    if (load_base == 0xFFFFFFFFu) return -1;

    info->entry = eh->entry;
    info->load_base = load_base;
    info->load_end = load_end;
    info->brk = (load_end + PAGE_SIZE - 1) & ~(PAGE_SIZE - 1);
    debug_log("ELF PT_LOAD mapped");
    return 0;
}
