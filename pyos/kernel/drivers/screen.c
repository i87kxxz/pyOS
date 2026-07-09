#include "screen.h"
#include "debug.h"
#include "io.h"

static int cursor_row = 0;
static int cursor_col = 0;
static u8 text_color = 0x0F;

void screen_init(void) {
    cursor_row = 0;
    cursor_col = 0;
    text_color = 0x0F;
}

void screen_clear(void) {
    for (int i = 0; i < VGA_WIDTH * VGA_HEIGHT; i++) {
        VGA_MEMORY[i] = (u16)(' ' | (0x07 << 8));
    }
    cursor_row = 0;
    cursor_col = 0;
}

void screen_set_color(u8 fg, u8 bg) {
    text_color = (u8)((bg << 4) | (fg & 0x0F));
}

void screen_set_cursor(int row, int col) {
    if (row < 0 || row >= VGA_HEIGHT || col < 0 || col >= VGA_WIDTH) {
        pyos_panic(
            "@kernel Screen.set_cursor",
            "Cursor position is outside the VGA text screen (0..24 rows, 0..79 cols)",
            "Use row between 0 and 24, col between 0 and 79"
        );
    }
    cursor_row = row;
    cursor_col = col;
}

void screen_get_cursor(int *row, int *col) {
    if (row) *row = cursor_row;
    if (col) *col = cursor_col;
}

static void screen_scroll(void) {
    for (int row = 1; row < VGA_HEIGHT; row++) {
        for (int col = 0; col < VGA_WIDTH; col++) {
            VGA_MEMORY[(row - 1) * VGA_WIDTH + col] =
                VGA_MEMORY[row * VGA_WIDTH + col];
        }
    }
    for (int col = 0; col < VGA_WIDTH; col++) {
        VGA_MEMORY[(VGA_HEIGHT - 1) * VGA_WIDTH + col] =
            (u16)(' ' | (text_color << 8));
    }
    cursor_row = VGA_HEIGHT - 1;
}

void screen_putchar(char c) {
    if (c == '\n') {
        cursor_col = 0;
        cursor_row++;
        if (cursor_row >= VGA_HEIGHT) screen_scroll();
        return;
    }
    if (c == '\r') {
        cursor_col = 0;
        return;
    }
    if (c == '\b') {
        if (cursor_col > 0) {
            cursor_col--;
            VGA_MEMORY[cursor_row * VGA_WIDTH + cursor_col] =
                (u16)(' ' | (text_color << 8));
        }
        return;
    }

    VGA_MEMORY[cursor_row * VGA_WIDTH + cursor_col] =
        (u16)((u8)c | (text_color << 8));
    cursor_col++;
    if (cursor_col >= VGA_WIDTH) {
        cursor_col = 0;
        cursor_row++;
        if (cursor_row >= VGA_HEIGHT) screen_scroll();
    }
}

void screen_print(const char *text) {
    if (!text) return;
    while (*text) {
        screen_putchar(*text++);
    }
}

void screen_print_at(const char *text, int row, int col, u8 color) {
    if (row < 0 || row >= VGA_HEIGHT || col < 0 || col >= VGA_WIDTH) {
        pyos_panic(
            "@kernel Screen.print",
            "Print position is outside the VGA text screen (0..24 rows, 0..79 cols)",
            "Pass a valid row/col, or omit them to use the cursor"
        );
    }
    int r = row;
    int c = col;
    if (!text) return;
    while (*text && r < VGA_HEIGHT) {
        if (*text == '\n') {
            r++;
            c = col;
            text++;
            continue;
        }
        if (c >= VGA_WIDTH) {
            r++;
            c = 0;
            if (r >= VGA_HEIGHT) break;
        }
        VGA_MEMORY[r * VGA_WIDTH + c] = (u16)((u8)(*text) | (color << 8));
        c++;
        text++;
    }
    cursor_row = r;
    cursor_col = 0;
}

void screen_print_char_at(char ch, int row, int col, u8 color) {
    if (row < 0 || row >= VGA_HEIGHT || col < 0 || col >= VGA_WIDTH) {
        pyos_panic(
            "@kernel Screen.print_char",
            "Character position is outside the VGA text screen",
            "Use row 0..24 and col 0..79"
        );
    }
    VGA_MEMORY[row * VGA_WIDTH + col] = (u16)((u8)ch | (color << 8));
}

void screen_scroll_up(int lines) {
    if (lines < 1) lines = 1;
    for (int n = 0; n < lines; n++) screen_scroll();
}

void screen_scroll_down(int lines) {
    /* Approximate: clear bottom and shift down once per line */
    if (lines < 1) lines = 1;
    for (int n = 0; n < lines; n++) {
        for (int row = VGA_HEIGHT - 2; row >= 0; row--) {
            for (int col = 0; col < VGA_WIDTH; col++) {
                VGA_MEMORY[(row + 1) * VGA_WIDTH + col] =
                    VGA_MEMORY[row * VGA_WIDTH + col];
            }
        }
        for (int col = 0; col < VGA_WIDTH; col++) {
            VGA_MEMORY[col] = (u16)(' ' | (text_color << 8));
        }
    }
}

void screen_enable_cursor(void) {
    outb(0x3D4, 0x0A);
    outb(0x3D5, (u8)(inb(0x3D5) & 0xC0));
    outb(0x3D4, 0x0B);
    outb(0x3D5, (u8)((inb(0x3D5) & 0xE0) | 15));
}

void screen_disable_cursor(void) {
    outb(0x3D4, 0x0A);
    outb(0x3D5, 0x20);
}
