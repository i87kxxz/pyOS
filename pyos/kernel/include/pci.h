#ifndef PYOS_PCI_H
#define PYOS_PCI_H

#include "types.h"

#define PCI_VENDOR_VIRTIO     0x1AF4u
#define PCI_DEVICE_VIRTIO_NET 0x1000u  /* legacy virtio-net */
#define PCI_DEVICE_VIRTIO_BLK 0x1001u  /* legacy virtio-blk */
#define PCI_DEVICE_VIRTIO_NET_MODERN 0x1041u
#define PCI_DEVICE_VIRTIO_BLK_MODERN 0x1042u

u32 pci_config_read(u8 bus, u8 slot, u8 func, u8 offset);
void pci_config_write(u8 bus, u8 slot, u8 func, u8 offset, u32 value);

/* Find first matching device; returns 1 and fills *bus/*slot/*func, else 0. */
i32 pci_find_device(u16 vendor, u16 device, u8 *bus, u8 *slot, u8 *func);

/* BAR0 I/O base for legacy virtio (0 if MMIO / missing). */
u16 pci_bar0_io(u8 bus, u8 slot, u8 func);

#endif
