#ifndef PYOS_VIRTIO_BLK_H
#define PYOS_VIRTIO_BLK_H

#include "types.h"

/* Probe PCI virtio-blk and register with blkdev. Returns 0 on success. */
i32 virtio_blk_init(void);

#endif
