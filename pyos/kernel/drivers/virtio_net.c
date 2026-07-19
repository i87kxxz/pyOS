#include "virtio_net.h"
#include "pci.h"
#include "io.h"
#include "pmm.h"
#include "heap.h"
#include "string.h"
#include "debug.h"

#define VIRTIO_ACKNOWLEDGE  1u
#define VIRTIO_DRIVER       2u
#define VIRTIO_DRIVER_OK    4u
#define VIRTIO_FAILED       128u

#define VRING_DESC_F_NEXT  1u
#define VRING_DESC_F_WRITE 2u

#define VIRTIO_NET_F_MAC 5u

#define QUEUE_MAX 256u
#define RX_BUF_SIZE 2048u
#define TX_BUF_SIZE 2048u
#define RX_BUFFERS 16u

struct virtq_desc {
    u64 addr;
    u32 len;
    u16 flags;
    u16 next;
} __attribute__((packed));

struct virtio_net_hdr {
    u8 flags;
    u8 gso_type;
    u16 hdr_len;
    u16 gso_size;
    u16 csum_start;
    u16 csum_offset;
} __attribute__((packed));

struct vq {
    u16 size;
    struct virtq_desc *desc;
    volatile u16 *avail_flags;
    volatile u16 *avail_idx;
    volatile u16 *avail_ring;
    volatile u16 *used_flags;
    volatile u16 *used_idx_ptr;
    volatile u32 *used_ring;
    u16 last_used;
    u8 *mem;
};

static u16 io_base;
static struct vq rxq;
static struct vq txq;
static u8 mac[6];
static u8 *rx_bufs[RX_BUFFERS];
static u8 *tx_buf;
static pyos_bool ready;

static void vset_status(u8 status) { outb(io_base + 18, status); }
static u8 vget_status(void) { return inb(io_base + 18); }
static void vreset(void) { outb(io_base + 18, 0); }

static u32 align_up(u32 v, u32 a) {
    return (v + a - 1u) & ~(a - 1u);
}

static i32 setup_queue(struct vq *q, u16 index) {
    outw(io_base + 14, index);
    u16 qsz = inw(io_base + 12);
    if (qsz == 0 || qsz > QUEUE_MAX) {
        debug_log("virtio-net: bad queue size");
        return -1;
    }
    q->size = qsz;

    u32 desc_bytes = 16u * qsz;
    u32 avail_bytes = 4u + 2u * qsz;
    u32 used_off = align_up(desc_bytes + avail_bytes, 4096u);
    u32 used_bytes = 4u + 8u * qsz;
    u32 total = used_off + used_bytes;
    u32 alloc = align_up(total, 4096u) + 4096u;

    u8 *raw = (u8 *)heap_malloc(alloc + 4096u);
    if (!raw) return -1;
    u32 aligned = align_up((u32)raw, 4096u);
    q->mem = (u8 *)aligned;
    memset(q->mem, 0, alloc);

    q->desc = (struct virtq_desc *)q->mem;
    q->avail_flags = (volatile u16 *)(q->mem + desc_bytes);
    q->avail_idx = q->avail_flags + 1;
    q->avail_ring = q->avail_flags + 2;
    q->used_flags = (volatile u16 *)(q->mem + used_off);
    q->used_idx_ptr = q->used_flags + 1;
    q->used_ring = (volatile u32 *)(q->used_flags + 2);
    *q->avail_flags = 0;
    *q->avail_idx = 0;
    *q->used_flags = 0;
    *q->used_idx_ptr = 0;
    q->last_used = 0;

    outl(io_base + 8, ((u32)q->mem) >> 12);
    return 0;
}

static void post_rx(u16 slot) {
    u8 *buf = rx_bufs[slot];
    memset(buf, 0, sizeof(struct virtio_net_hdr));
    rxq.desc[slot].addr = (u64)(u32)buf;
    rxq.desc[slot].len = RX_BUF_SIZE;
    rxq.desc[slot].flags = VRING_DESC_F_WRITE;
    rxq.desc[slot].next = 0;

    u16 aidx = (u16)((*rxq.avail_idx) % rxq.size);
    rxq.avail_ring[aidx] = slot;
    __asm__ volatile("" ::: "memory");
    (*rxq.avail_idx)++;
    outw(io_base + 16, 0); /* notify RX */
}

i32 virtio_net_init(void) {
    u8 bus, slot, func;
    ready = PYOS_FALSE;
    io_base = 0;
    memset(&rxq, 0, sizeof(rxq));
    memset(&txq, 0, sizeof(txq));

    if (!pci_find_device(PCI_VENDOR_VIRTIO, PCI_DEVICE_VIRTIO_NET, &bus, &slot, &func)) {
        if (!pci_find_device(PCI_VENDOR_VIRTIO, PCI_DEVICE_VIRTIO_NET_MODERN, &bus, &slot, &func)) {
            debug_log("virtio-net: no PCI device");
            return -1;
        }
    }

    u32 cmd = pci_config_read(bus, slot, func, 0x04);
    cmd |= 0x5u;
    pci_config_write(bus, slot, func, 0x04, cmd);

    io_base = pci_bar0_io(bus, slot, func);
    if (!io_base) {
        debug_log("virtio-net: BAR0 not I/O (need legacy)");
        return -1;
    }

    vreset();
    vset_status(VIRTIO_ACKNOWLEDGE);
    vset_status((u8)(VIRTIO_ACKNOWLEDGE | VIRTIO_DRIVER));

    u32 feats = inl(io_base + 0);
    u32 guest = 0;
    if (feats & (1u << VIRTIO_NET_F_MAC)) guest |= (1u << VIRTIO_NET_F_MAC);
    outl(io_base + 4, guest);

    for (int i = 0; i < 6; i++) mac[i] = inb(io_base + 20 + i);

    if (setup_queue(&rxq, 0) != 0) {
        debug_log("virtio-net: RX queue fail");
        return -1;
    }
    if (setup_queue(&txq, 1) != 0) {
        debug_log("virtio-net: TX queue fail");
        return -1;
    }

    for (u32 i = 0; i < RX_BUFFERS; i++) {
        rx_bufs[i] = (u8 *)pmm_alloc_page();
        if (!rx_bufs[i]) rx_bufs[i] = (u8 *)heap_malloc(RX_BUF_SIZE);
        if (!rx_bufs[i]) {
            debug_log("virtio-net: no RX buffer");
            return -1;
        }
        memset(rx_bufs[i], 0, RX_BUF_SIZE);
    }
    tx_buf = (u8 *)pmm_alloc_page();
    if (!tx_buf) tx_buf = (u8 *)heap_malloc(TX_BUF_SIZE);
    if (!tx_buf) {
        debug_log("virtio-net: no TX buffer");
        return -1;
    }
    memset(tx_buf, 0, TX_BUF_SIZE);

    u16 n = RX_BUFFERS < rxq.size ? RX_BUFFERS : rxq.size;
    for (u16 i = 0; i < n; i++) post_rx(i);

    vset_status((u8)(VIRTIO_ACKNOWLEDGE | VIRTIO_DRIVER | VIRTIO_DRIVER_OK));
    if (vget_status() & VIRTIO_FAILED) {
        debug_log("virtio-net: device failed");
        return -1;
    }

    ready = PYOS_TRUE;
    debug_log("virtio-net: ready");
    return 0;
}

pyos_bool virtio_net_is_ready(void) { return ready; }

void virtio_net_get_mac(u8 out[6]) {
    for (int i = 0; i < 6; i++) out[i] = mac[i];
}

i32 virtio_net_tx(const void *frame, u32 len) {
    if (!ready || !frame || len == 0 || len + sizeof(struct virtio_net_hdr) > TX_BUF_SIZE)
        return -1;

    struct virtio_net_hdr *hdr = (struct virtio_net_hdr *)tx_buf;
    memset(hdr, 0, sizeof(*hdr));
    memcpy(tx_buf + sizeof(*hdr), frame, len);

    /* Wait for prior TX if any */
    for (u32 spin = 0; spin < 2000000u; spin++) {
        __asm__ volatile("" ::: "memory");
        if (*txq.used_idx_ptr == txq.last_used) break;
        txq.last_used = *txq.used_idx_ptr;
        break;
    }

    txq.desc[0].addr = (u64)(u32)tx_buf;
    txq.desc[0].len = (u32)(sizeof(*hdr) + len);
    txq.desc[0].flags = 0;
    txq.desc[0].next = 0;

    u16 aidx = (u16)((*txq.avail_idx) % txq.size);
    txq.avail_ring[aidx] = 0;
    __asm__ volatile("" ::: "memory");
    (*txq.avail_idx)++;
    outw(io_base + 16, 1); /* notify TX */

    for (u32 spin = 0; spin < 4000000u; spin++) {
        __asm__ volatile("" ::: "memory");
        if (*txq.used_idx_ptr != txq.last_used) {
            txq.last_used = *txq.used_idx_ptr;
            return 0;
        }
    }
    debug_log("virtio-net: TX timeout");
    return -1;
}

i32 virtio_net_rx(void *buf, u32 maxlen) {
    if (!ready || !buf || maxlen == 0) return 0;

    __asm__ volatile("" ::: "memory");
    if (*rxq.used_idx_ptr == rxq.last_used) return 0;

    u16 uidx = (u16)(rxq.last_used % rxq.size);
    u32 id = rxq.used_ring[uidx * 2];
    u32 plen = rxq.used_ring[uidx * 2 + 1];
    rxq.last_used++;

    if (id >= RX_BUFFERS) {
        return 0;
    }

    u8 *raw = rx_bufs[id];
    u32 payload = plen > sizeof(struct virtio_net_hdr)
                      ? plen - (u32)sizeof(struct virtio_net_hdr)
                      : 0;
    if (payload > maxlen) payload = maxlen;
    if (payload) memcpy(buf, raw + sizeof(struct virtio_net_hdr), payload);

    post_rx((u16)id);
    return (i32)payload;
}
