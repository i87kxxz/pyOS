#ifndef PYOS_SCREEN_H
#define PYOS_SCREEN_H

#include "types.h"

#define VGA_WIDTH  80
#define VGA_HEIGHT 25
#define VGA_MEMORY ((volatile u16*)0xB8000)

void screen_init(void);
void screen_clear(void);
void screen_set_color(u8 fg, u8 bg);
void screen_set_cursor(int row, int col);
void screen_get_cursor(int *row, int *col);
void screen_putchar(char c);
void screen_print(const char *text);
void screen_print_at(const char *text, int row, int col, u8 color);
void screen_print_char_at(char c, int row, int col, u8 color);

#endif
