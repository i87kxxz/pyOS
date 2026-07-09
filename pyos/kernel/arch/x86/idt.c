#include "idt.h"
#include "pic.h"
#include "keyboard.h"
#include "io.h"
#include "debug.h"
#include "syscall.h"
#include "types.h"
#include "timer.h"

struct idt_entry {
    u16 base_lo;
    u16 sel;
    u8  always0;
    u8  flags;
    u16 base_hi;
} __attribute__((packed));

struct idt_ptr {
    u16 limit;
    u32 base;
} __attribute__((packed));

static struct idt_entry idt[256];
static struct idt_ptr idtp;

extern void isr_stub_0(void);
extern void isr_stub_1(void);
extern void isr_stub_2(void);
extern void isr_stub_3(void);
extern void isr_stub_4(void);
extern void isr_stub_5(void);
extern void isr_stub_6(void);
extern void isr_stub_7(void);
extern void isr_stub_8(void);
extern void isr_stub_9(void);
extern void isr_stub_10(void);
extern void isr_stub_11(void);
extern void isr_stub_12(void);
extern void isr_stub_13(void);
extern void isr_stub_14(void);
extern void isr_stub_15(void);
extern void isr_stub_16(void);
extern void isr_stub_17(void);
extern void isr_stub_18(void);
extern void isr_stub_19(void);
extern void isr_stub_20(void);
extern void isr_stub_21(void);
extern void isr_stub_22(void);
extern void isr_stub_23(void);
extern void isr_stub_24(void);
extern void isr_stub_25(void);
extern void isr_stub_26(void);
extern void isr_stub_27(void);
extern void isr_stub_28(void);
extern void isr_stub_29(void);
extern void isr_stub_30(void);
extern void isr_stub_31(void);
extern void irq_stub_0(void);
extern void irq_stub_1(void);
extern void irq_stub_2(void);
extern void irq_stub_3(void);
extern void irq_stub_4(void);
extern void irq_stub_5(void);
extern void irq_stub_6(void);
extern void irq_stub_7(void);
extern void irq_stub_8(void);
extern void irq_stub_9(void);
extern void irq_stub_10(void);
extern void irq_stub_11(void);
extern void irq_stub_12(void);
extern void irq_stub_13(void);
extern void irq_stub_14(void);
extern void irq_stub_15(void);
extern void isr_stub_128(void);

void idt_set_gate(u8 num, u32 handler, u16 selector, u8 flags) {
    idt[num].base_lo = (u16)(handler & 0xFFFF);
    idt[num].base_hi = (u16)((handler >> 16) & 0xFFFF);
    idt[num].sel = selector;
    idt[num].always0 = 0;
    idt[num].flags = flags;
}

static void lidt(struct idt_ptr *ptr) {
    __asm__ volatile ("lidt (%0)" : : "r"(ptr));
}

void fault_handler(u32 int_no, u32 err_code, u32 eip) {
    (void)err_code;
    const char *names[] = {
        "Divide by zero", "Debug", "NMI", "Breakpoint", "Overflow",
        "Bound range", "Invalid opcode", "Device not available",
        "Double fault", "Coprocessor segment", "Invalid TSS",
        "Segment not present", "Stack fault", "General protection fault",
        "Page fault", "Reserved", "x87 FPU error", "Alignment check",
        "Machine check", "SIMD FPU error"
    };
    const char *name = (int_no < 20) ? names[int_no] : "Unknown exception";
    pyos_panic_at(
        "CPU exception in kernel",
        name,
        "This usually means bad memory access, invalid instruction, or a bug in generated glue",
        eip
    );
}

void irq_handler(u32 irq) {
    if (irq == 0) {
        pit_irq();
    } else if (irq == 1) {
        keyboard_irq_handler();
    }
    pic_send_eoi((u8)irq);
}

void syscall_handler_c(u32 num, u32 a1, u32 a2, u32 a3) {
    (void)syscall_dispatch(num, a1, a2, a3);
}

void idt_init(void) {
    for (int i = 0; i < 256; i++) {
        idt_set_gate((u8)i, 0, 0x08, 0);
    }

    void (*isrs[])(void) = {
        isr_stub_0, isr_stub_1, isr_stub_2, isr_stub_3, isr_stub_4,
        isr_stub_5, isr_stub_6, isr_stub_7, isr_stub_8, isr_stub_9,
        isr_stub_10, isr_stub_11, isr_stub_12, isr_stub_13, isr_stub_14,
        isr_stub_15, isr_stub_16, isr_stub_17, isr_stub_18, isr_stub_19,
        isr_stub_20, isr_stub_21, isr_stub_22, isr_stub_23, isr_stub_24,
        isr_stub_25, isr_stub_26, isr_stub_27, isr_stub_28, isr_stub_29,
        isr_stub_30, isr_stub_31
    };
    for (int i = 0; i < 32; i++) {
        idt_set_gate((u8)i, (u32)isrs[i], 0x08, 0x8E);
    }

    void (*irqs[])(void) = {
        irq_stub_0, irq_stub_1, irq_stub_2, irq_stub_3,
        irq_stub_4, irq_stub_5, irq_stub_6, irq_stub_7,
        irq_stub_8, irq_stub_9, irq_stub_10, irq_stub_11,
        irq_stub_12, irq_stub_13, irq_stub_14, irq_stub_15
    };
    for (int i = 0; i < 16; i++) {
        idt_set_gate((u8)(32 + i), (u32)irqs[i], 0x08, 0x8E);
    }

    idt_set_gate(0x80, (u32)isr_stub_128, 0x08, 0xEE);

    idtp.limit = (u16)(sizeof(idt) - 1);
    idtp.base = (u32)&idt;
    lidt(&idtp);
}

void irq_install_handlers(void) {
    /* gates already installed in idt_init */
}
