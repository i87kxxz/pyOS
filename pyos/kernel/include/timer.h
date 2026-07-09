#ifndef PYOS_TIMER_H
#define PYOS_TIMER_H

#include "types.h"

void pit_init(u32 hz);
void pit_irq(void);
u32 timer_ticks(void);
u32 timer_ms(void);
void timer_sleep_ms(u32 ms);

#endif
