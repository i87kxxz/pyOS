#include "blkdev.h"
#include "virtio_blk.h"
#include "debug.h"

/* Forward decls from virtio_blk.c */
i32 virtio_blk_read_sectors(u64 sector, void *buf, u32 count);
i32 virtio_blk_write_sectors(u64 sector, const void *buf, u32 count);
u64 virtio_blk_capacity(void);
pyos_bool virtio_blk_is_ready(void);

static BlkInfo info;

void blkdev_init(void) {
    info.present = PYOS_FALSE;
    info.sectors = 0;
    if (virtio_blk_init() == 0 && virtio_blk_is_ready()) {
        info.present = PYOS_TRUE;
        info.sectors = virtio_blk_capacity();
        debug_log("blkdev: virtio-blk attached");
    } else {
        debug_log("blkdev: no block device");
    }
}

pyos_bool blkdev_ready(void) {
    return info.present;
}

BlkInfo blkdev_info(void) {
    return info;
}

i32 blkdev_read(u64 sector, void *buf, u32 count) {
    if (!info.present || !buf || count == 0) return -1;
    if (sector + count > info.sectors && info.sectors != 0) return -1;
    /* virtio_blk_xfer caps at 2048 bytes (4 sectors) — chunk larger FS blocks. */
    u8 *dst = (u8 *)buf;
    while (count) {
        u32 n = count > 4u ? 4u : count;
        if (virtio_blk_read_sectors(sector, dst, n) != 0) return -1;
        sector += n;
        dst += n * BLK_SECTOR_SIZE;
        count -= n;
    }
    return 0;
}

i32 blkdev_write(u64 sector, const void *buf, u32 count) {
    if (!info.present || !buf || count == 0) return -1;
    if (sector + count > info.sectors && info.sectors != 0) return -1;
    const u8 *src = (const u8 *)buf;
    while (count) {
        u32 n = count > 4u ? 4u : count;
        if (virtio_blk_write_sectors(sector, src, n) != 0) return -1;
        sector += n;
        src += n * BLK_SECTOR_SIZE;
        count -= n;
    }
    return 0;
}
