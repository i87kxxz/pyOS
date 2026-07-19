#ifndef PYOS_VIRTIO_NET_H
#define PYOS_VIRTIO_NET_H

#include "types.h"

i32 virtio_net_init(void);
pyos_bool virtio_net_is_ready(void);
void virtio_net_get_mac(u8 mac[6]);

/* Transmit one Ethernet frame (dst/src/type already in frame). Returns 0 or -1. */
i32 virtio_net_tx(const void *frame, u32 len);

/* Poll RX; if a frame is available, copy up to *len bytes and return length, else 0. */
i32 virtio_net_rx(void *buf, u32 maxlen);

#endif
