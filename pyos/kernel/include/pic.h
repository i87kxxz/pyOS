#ifndef PYOS_PIC_H
#define PYOS_PIC_H

#include "types.h"

void pic_remap(u8 offset1, u8 offset2);
void pic_send_eoi(u8 irq);
void pic_set_mask(u8 irq_line);
void pic_clear_mask(u8 irq_line);
static inline void pic_mask_irq(u8 irq) { pic_set_mask(irq); }
static inline void pic_unmask_irq(u8 irq) { pic_clear_mask(irq); }
void pic_init(void);

#endif
