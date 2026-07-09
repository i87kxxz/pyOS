#ifndef PYOS_IDT_H
#define PYOS_IDT_H

#include "types.h"

void idt_init(void);
void idt_set_gate(u8 num, u32 handler, u16 selector, u8 flags);
void irq_install_handlers(void);

#endif
