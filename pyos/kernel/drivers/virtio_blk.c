#include "virtio_blk.h"
#include "pci.h"
#include "io.h"
#include "pmm.h"
#include "heap.h"
#include "string.h"
#include "debug.h"
#include "blkdev.h"

#define VIRTIO_ACKNOWLEDGE  1u
#define VIRTIO_DRIVER       2u
#define VIRTIO_DRIVER_OK    4u
#define VIRTIO_FAILED       128u

#define VRING_DESC_F_NEXT  1u
#define VRING_DESC_F_WRITE 2u

#define VIRTIO_BLK_T_IN  0u
#define VIRTIO_BLK_T_OUT 1u

#define QUEUE_MAX 256u

struct virtq_desc {
    u64 addr;
    u32 len;
    u16 flags;
    u16 next;
} __attribute__((packed));

struct virtio_blk_req {
    u32 type;
    u32 reserved;
    u64 sector;
} __attribute__((packed));

static u16 io_base;
static u16 queue_size;
static struct virtq_desc *desc;
static volatile u16 *avail_flags;
static volatile u16 *avail_idx;
static volatile u16 *avail_ring;
static volatile u16 *used_flags;
static volatile u16 *used_idx_ptr;
static volatile u32 *used_ring; /* pairs of id,len */
static u16 last_used_idx;
static u8 *req_page;
static u8 *queue_mem;
static pyos_bool ready;

static void vset_status(u8 status) {
    outb(io_base + 18, status);
}

static u8 vget_status(void) {
    return inb(io_base + 18);
}

static void vreset(void) {
    outb(io_base + 18, 0);
}

static u32 align_up(u32 v, u32 a) {
    return (v + a - 1u) & ~(a - 1u);
}

i32 virtio_blk_init(void) {
    u8 bus, slot, func;
    ready = PYOS_FALSE;
    io_base = 0;
    queue_mem = 0;

    if (!pci_find_device(PCI_VENDOR_VIRTIO, PCI_DEVICE_VIRTIO_BLK, &bus, &slot, &func)) {
        if (!pci_find_device(PCI_VENDOR_VIRTIO, PCI_DEVICE_VIRTIO_BLK_MODERN, &bus, &slot, &func)) {
            debug_log("virtio-blk: no PCI device");
            return -1;
        }
    }

    u32 cmd = pci_config_read(bus, slot, func, 0x04);
    cmd |= 0x5u;
    pci_config_write(bus, slot, func, 0x04, cmd);

    io_base = pci_bar0_io(bus, slot, func);
    if (!io_base) {
        debug_log("virtio-blk: BAR0 not I/O (need legacy)");
        return -1;
    }

    vreset();
    vset_status(VIRTIO_ACKNOWLEDGE);
    vset_status((u8)(VIRTIO_ACKNOWLEDGE | VIRTIO_DRIVER));

    (void)inl(io_base + 0);
    outl(io_base + 4, 0);

    outw(io_base + 14, 0);
    queue_size = inw(io_base + 12);
    if (queue_size == 0 || queue_size > QUEUE_MAX) {
        debug_log("virtio-blk: bad queue size");
        vset_status(VIRTIO_FAILED);
        return -1;
    }

    u32 desc_bytes = 16u * queue_size;
    u32 avail_bytes = 4u + 2u * queue_size;
    u32 used_off = align_up(desc_bytes + avail_bytes, 4096u);
    u32 used_bytes = 4u + 8u * queue_size;
    u32 total = used_off + used_bytes;
    u32 alloc = align_up(total, 4096u) + 4096u;

    u8 *raw = (u8 *)heap_malloc(alloc + 4096u);
    if (!raw) {
        debug_log("virtio-blk: no memory for queue");
        return -1;
    }
    u32 aligned = align_up((u32)raw, 4096u);
    queue_mem = (u8 *)aligned;
    memset(queue_mem, 0, alloc);

    desc = (struct virtq_desc *)queue_mem;
    avail_flags = (volatile u16 *)(queue_mem + desc_bytes);
    avail_idx = avail_flags + 1;
    avail_ring = avail_flags + 2;
    used_flags = (volatile u16 *)(queue_mem + used_off);
    used_idx_ptr = used_flags + 1;
    used_ring = (volatile u32 *)(used_flags + 2);
    *avail_flags = 0;
    *avail_idx = 0;
    *used_flags = 0;
    *used_idx_ptr = 0;
    last_used_idx = 0;

    outl(io_base + 8, ((u32)queue_mem) >> 12);

    req_page = (u8 *)pmm_alloc_page();
    if (!req_page) req_page = (u8 *)heap_malloc(4096);
    if (!req_page) {
        debug_log("virtio-blk: no request buffer");
        return -1;
    }
    memset(req_page, 0, 4096);

    vset_status((u8)(VIRTIO_ACKNOWLEDGE | VIRTIO_DRIVER | VIRTIO_DRIVER_OK));
    if (vget_status() & VIRTIO_FAILED) {
        debug_log("virtio-blk: device failed");
        return -1;
    }

    ready = PYOS_TRUE;
    debug_log("virtio-blk: ready");
    return 0;
}

static i32 virtio_blk_xfer(u32 type, u64 sector, void *buf, u32 bytes) {
    if (!ready || !buf || bytes == 0 || (bytes % BLK_SECTOR_SIZE) != 0) return -1;
    if (bytes > 2048u) return -1;

    struct virtio_blk_req *hdr = (struct virtio_blk_req *)req_page;
    u8 *data = req_page + 512;
    u8 *status = req_page + 512 + 2048;

    hdr->type = type;
    hdr->reserved = 0;
    hdr->sector = sector;
    *status = 0xFF;

    if (type == VIRTIO_BLK_T_OUT) memcpy(data, buf, bytes);
    else memset(data, 0, bytes);

    desc[0].addr = (u64)(u32)hdr;
    desc[0].len = sizeof(*hdr);
    desc[0].flags = VRING_DESC_F_NEXT;
    desc[0].next = 1;

    desc[1].addr = (u64)(u32)data;
    desc[1].len = bytes;
    desc[1].flags = (u16)(VRING_DESC_F_NEXT | (type == VIRTIO_BLK_T_IN ? VRING_DESC_F_WRITE : 0));
    desc[1].next = 2;

    desc[2].addr = (u64)(u32)status;
    desc[2].len = 1;
    desc[2].flags = VRING_DESC_F_WRITE;
    desc[2].next = 0;

    u16 aidx = (u16)((*avail_idx) % queue_size);
    avail_ring[aidx] = 0;
    __asm__ volatile ("" ::: "memory");
    (*avail_idx)++;

    outw(io_base + 16, 0);

    for (u32 spin = 0; spin < 4000000u; spin++) {
        __asm__ volatile ("" ::: "memory");
        if (*used_idx_ptr != last_used_idx) {
            last_used_idx = *used_idx_ptr;
            if (*status != 0) {
                debug_log("virtio-blk: I/O status error");
                return -1;
            }
            if (type == VIRTIO_BLK_T_IN) memcpy(buf, data, bytes);
            return 0;
        }
    }
    debug_log("virtio-blk: I/O timeout");
    return -1;
}

i32 virtio_blk_read_sectors(u64 sector, void *buf, u32 count) {
    return virtio_blk_xfer(VIRTIO_BLK_T_IN, sector, buf, count * BLK_SECTOR_SIZE);
}

i32 virtio_blk_write_sectors(u64 sector, const void *buf, u32 count) {
    return virtio_blk_xfer(VIRTIO_BLK_T_OUT, sector, (void *)buf, count * BLK_SECTOR_SIZE);
}

u64 virtio_blk_capacity(void) {
    if (!ready || !io_base) return 0;
    u32 lo = inl(io_base + 20);
    u32 hi = inl(io_base + 24);
    return ((u64)hi << 32) | lo;
}

pyos_bool virtio_blk_is_ready(void) {
    return ready;
}
