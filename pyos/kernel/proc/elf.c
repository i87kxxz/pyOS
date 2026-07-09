#include "elf.h"

/* Flat binary loader: entry = load address (image already in memory). */
i32 elf_load_flat(const u8 *image, u32 size, u32 *entry_out) {
    if (!image || size < 4 || !entry_out) return -1;
    /* Accept raw entry pointer stored in first 4 bytes as little-endian */
    u32 entry = (u32)image[0] | ((u32)image[1] << 8) | ((u32)image[2] << 16) | ((u32)image[3] << 24);
    if (entry == 0) entry = (u32)image;
    *entry_out = entry;
    return 0;
}
