#include "pic.h"
#include "io.h"

#define PIC1         0x20
#define PIC2         0xA0
#define PIC1_COMMAND PIC1
#define PIC1_DATA    (PIC1 + 1)
#define PIC2_COMMAND PIC2
#define PIC2_DATA    (PIC2 + 1)
#define PIC_EOI      0x20

void pic_send_eoi(u8 irq) {
    if (irq >= 8) outb(PIC2_COMMAND, PIC_EOI);
    outb(PIC1_COMMAND, PIC_EOI);
}

void pic_set_mask(u8 irq_line) {
    u16 port;
    u8 value;
    if (irq_line < 8) {
        port = PIC1_DATA;
    } else {
        port = PIC2_DATA;
        irq_line = (u8)(irq_line - 8);
    }
    value = (u8)(inb(port) | (1 << irq_line));
    outb(port, value);
}

void pic_clear_mask(u8 irq_line) {
    u16 port;
    u8 value;
    if (irq_line < 8) {
        port = PIC1_DATA;
    } else {
        port = PIC2_DATA;
        irq_line = (u8)(irq_line - 8);
    }
    value = (u8)(inb(port) & ~(1 << irq_line));
    outb(port, value);
}

void pic_remap(u8 offset1, u8 offset2) {
    u8 a1 = inb(PIC1_DATA);
    u8 a2 = inb(PIC2_DATA);

    outb(PIC1_COMMAND, 0x11); io_wait();
    outb(PIC2_COMMAND, 0x11); io_wait();
    outb(PIC1_DATA, offset1); io_wait();
    outb(PIC2_DATA, offset2); io_wait();
    outb(PIC1_DATA, 4); io_wait();
    outb(PIC2_DATA, 2); io_wait();
    outb(PIC1_DATA, 0x01); io_wait();
    outb(PIC2_DATA, 0x01); io_wait();

    outb(PIC1_DATA, a1);
    outb(PIC2_DATA, a2);
}

void pic_init(void) {
    pic_remap(0x20, 0x28);
    /* Mask all, then enable timer+keyboard */
    outb(PIC1_DATA, 0xFC); /* unmask IRQ0 and IRQ1 */
    outb(PIC2_DATA, 0xFF);
}
