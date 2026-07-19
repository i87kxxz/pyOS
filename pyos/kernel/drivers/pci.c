#include "pci.h"
#include "io.h"

#define PCI_CONFIG_ADDR 0xCF8u
#define PCI_CONFIG_DATA 0xCFCu

u32 pci_config_read(u8 bus, u8 slot, u8 func, u8 offset) {
    u32 addr = (u32)(1u << 31) |
               ((u32)bus << 16) |
               ((u32)(slot & 0x1Fu) << 11) |
               ((u32)(func & 0x7u) << 8) |
               ((u32)offset & 0xFCu);
    outl(PCI_CONFIG_ADDR, addr);
    return inl(PCI_CONFIG_DATA);
}

void pci_config_write(u8 bus, u8 slot, u8 func, u8 offset, u32 value) {
    u32 addr = (u32)(1u << 31) |
               ((u32)bus << 16) |
               ((u32)(slot & 0x1Fu) << 11) |
               ((u32)(func & 0x7u) << 8) |
               ((u32)offset & 0xFCu);
    outl(PCI_CONFIG_ADDR, addr);
    outl(PCI_CONFIG_DATA, value);
}

i32 pci_find_device(u16 vendor, u16 device, u8 *bus_out, u8 *slot_out, u8 *func_out) {
    for (u16 bus = 0; bus < 256; bus++) {
        for (u8 slot = 0; slot < 32; slot++) {
            u32 id = pci_config_read((u8)bus, slot, 0, 0);
            u16 v = (u16)(id & 0xFFFFu);
            u16 d = (u16)(id >> 16);
            if (v == 0xFFFFu) continue;
            if (v == vendor && d == device) {
                if (bus_out) *bus_out = (u8)bus;
                if (slot_out) *slot_out = slot;
                if (func_out) *func_out = 0;
                return 1;
            }
            /* multi-function */
            u32 hdr = pci_config_read((u8)bus, slot, 0, 0x0C);
            if (((hdr >> 16) & 0x80u) == 0) continue;
            for (u8 func = 1; func < 8; func++) {
                id = pci_config_read((u8)bus, slot, func, 0);
                v = (u16)(id & 0xFFFFu);
                d = (u16)(id >> 16);
                if (v == 0xFFFFu) continue;
                if (v == vendor && d == device) {
                    if (bus_out) *bus_out = (u8)bus;
                    if (slot_out) *slot_out = slot;
                    if (func_out) *func_out = func;
                    return 1;
                }
            }
        }
    }
    return 0;
}

u16 pci_bar0_io(u8 bus, u8 slot, u8 func) {
    u32 bar = pci_config_read(bus, slot, func, 0x10);
    if ((bar & 1u) == 0) return 0; /* memory BAR */
    return (u16)(bar & ~0x3u);
}
