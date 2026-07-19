#ifndef PYOS_BLKDEV_H
#define PYOS_BLKDEV_H

#include "types.h"

#define BLK_SECTOR_SIZE 512u

typedef struct {
    pyos_bool present;
    u64 sectors; /* capacity in 512-byte sectors */
} BlkInfo;

void blkdev_init(void);
pyos_bool blkdev_ready(void);
BlkInfo blkdev_info(void);

/* Read/write 512-byte sectors. Returns 0 on success, -1 on error. */
i32 blkdev_read(u64 sector, void *buf, u32 count);
i32 blkdev_write(u64 sector, const void *buf, u32 count);

#endif
