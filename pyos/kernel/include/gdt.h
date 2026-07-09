#ifndef PYOS_GDT_H
#define PYOS_GDT_H

#include "types.h"

void gdt_init(void);
void tss_set_kernel_stack(u32 esp0);

#endif
