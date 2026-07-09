#ifndef PYOS_KEYBOARD_H
#define PYOS_KEYBOARD_H

#include "types.h"

typedef struct {
    u8 scancode;
    char ch;
    pyos_bool pressed;
    pyos_bool shift;
    pyos_bool ctrl;
    pyos_bool alt;
} KeyEvent;

typedef void (*keypress_handler_t)(KeyEvent *ev);

void keyboard_init(void);
void keyboard_irq_handler(void);
pyos_bool keyboard_has_key(void);
KeyEvent keyboard_read_key(void);
char keyboard_read_char(void);
void keyboard_set_handler(keypress_handler_t handler);

#endif
