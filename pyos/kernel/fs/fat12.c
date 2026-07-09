#include "fat12.h"
#include "floppy.h"
#include "vfs.h"
#include "debug.h"
#include "string.h"

void fat12_init(u32 image_lba_offset) {
    (void)image_lba_offset;
}

i32 fat12_load_seeds_into_vfs(void) {
    const u8 *base = floppy_seed_base();
    if (!base) return -1;
    u32 count = (u32)base[0] | ((u32)base[1] << 8) | ((u32)base[2] << 16) | ((u32)base[3] << 24);
    if (count == 0 || count > 32) return 0;
    const u8 *p = base + 4;
    for (u32 i = 0; i < count; i++) {
        char name[12];
        for (int j = 0; j < 11; j++) name[j] = (char)p[j];
        name[11] = 0;
        /* trim spaces */
        for (int j = 10; j >= 0; j--) {
            if (name[j] == ' ') name[j] = 0;
            else break;
        }
        p += 11;
        u32 size = (u32)p[0] | ((u32)p[1] << 8) | ((u32)p[2] << 16) | ((u32)p[3] << 24);
        p += 4;
        vfs_create(name, p, size);
        p += size;
        debug_log("FAT seed loaded into VFS");
    }
    return (i32)count;
}
