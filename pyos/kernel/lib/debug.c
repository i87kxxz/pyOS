#include "debug.h"
#include "io.h"
#include "screen.h"
#include "kernel.h"

#define COM1 0x3F8

void serial_init(void) {
    outb(COM1 + 1, 0x00);
    outb(COM1 + 3, 0x80);
    outb(COM1 + 0, 0x03);
    outb(COM1 + 1, 0x00);
    outb(COM1 + 3, 0x03);
    outb(COM1 + 2, 0xC7);
    outb(COM1 + 4, 0x0B);
}

pyos_bool serial_can_read(void) {
    return (inb(COM1 + 5) & 0x01) != 0;
}

i32 serial_read(void) {
    if (!serial_can_read()) return -1;
    return (i32)inb(COM1);
}

void serial_write(char c) {
    /* QEMU debugcon / Bochs port — always available in QEMU */
    outb(0xE9, (u8)c);

    /* COM1 with a short spin so we never hang forever if serial is missing */
    for (int i = 0; i < 100000; i++) {
        if (inb(COM1 + 5) & 0x20) {
            outb(COM1, (u8)c);
            return;
        }
    }
    outb(COM1, (u8)c);
}

void serial_write_str(const char *s) {
    if (!s) return;
    while (*s) {
        if (*s == '\n') serial_write('\r');
        serial_write(*s++);
    }
}

void serial_write_hex(u32 value) {
    const char *hex = "0123456789ABCDEF";
    serial_write_str("0x");
    for (int i = 7; i >= 0; i--) {
        serial_write(hex[(value >> (i * 4)) & 0xF]);
    }
}

void serial_write_dec(u32 value) {
    char buf[16];
    int i = 0;
    if (value == 0) {
        serial_write('0');
        return;
    }
    while (value > 0 && i < 15) {
        buf[i++] = (char)('0' + (value % 10));
        value /= 10;
    }
    while (i--) serial_write(buf[i]);
}

void debug_log(const char *msg) {
    /* Always emit boot/panic breadcrumbs to serial; quiet only suppresses spam later if needed */
    serial_write_str("[pyOS] ");
    serial_write_str(msg ? msg : "");
    serial_write_str("\n");
}

void debug_logf(const char *prefix, const char *msg) {
    serial_write_str("[pyOS] ");
    serial_write_str(prefix);
    serial_write_str(": ");
    serial_write_str(msg);
    serial_write_str("\n");
}

void pyos_panic(const char *where, const char *reason, const char *hint) {
    cli();
    serial_write_str("\n========== pyOS PANIC ==========\n");
    serial_write_str("Where : ");
    serial_write_str(where ? where : "(unknown)");
    serial_write_str("\n");
    serial_write_str("Why   : ");
    serial_write_str(reason ? reason : "(unknown)");
    serial_write_str("\n");
    if (hint && hint[0]) {
        serial_write_str("Hint  : ");
        serial_write_str(hint);
        serial_write_str("\n");
    }
    serial_write_str("================================\n");

    screen_set_color(15, 4);
    screen_print_at("pyOS PANIC", 0, 0, 0x4F);
    screen_print_at(where ? where : "unknown", 2, 0, 0x4F);
    screen_print_at(reason ? reason : "unknown", 3, 0, 0x4F);
    if (hint && hint[0]) {
        screen_print_at(hint, 5, 0, 0x4E);
    }

    for (;;) {
        hlt();
    }
}

void pyos_panic_at(const char *where, const char *reason, const char *hint, u32 eip) {
    serial_write_str("\n========== pyOS PANIC ==========\n");
    serial_write_str("Where : ");
    serial_write_str(where ? where : "(unknown)");
    serial_write_str("\n");
    serial_write_str("Why   : ");
    serial_write_str(reason ? reason : "(unknown)");
    serial_write_str("\n");
    if (hint && hint[0]) {
        serial_write_str("Hint  : ");
        serial_write_str(hint);
        serial_write_str("\n");
    }
    serial_write_str("Detail: EIP=");
    serial_write_hex(eip);
    serial_write_str(" (secondary technical detail)\n");
    serial_write_str("================================\n");

    cli();
    screen_set_color(15, 4);
    screen_print_at("pyOS PANIC", 0, 0, 0x4F);
    screen_print_at(where ? where : "unknown", 2, 0, 0x4F);
    screen_print_at(reason ? reason : "unknown", 3, 0, 0x4F);
    for (;;) {
        hlt();
    }
}
