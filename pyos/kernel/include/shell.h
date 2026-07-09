#ifndef PYOS_SHELL_H
#define PYOS_SHELL_H

#include "types.h"

void shell_init(void);
void shell_on_key(char ch, u8 scancode);
void shell_on_timer(void);
void shell_run_line(const char *line);

#endif
