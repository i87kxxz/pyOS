#include "keyboard.h"
#include "io.h"
#include "debug.h"
#include "kernel.h"

#define KB_DATA   0x60
#define KB_STATUS 0x64
#define BUF_SIZE  64

static KeyEvent buffer[BUF_SIZE];
static int buf_head = 0;
static int buf_tail = 0;
static pyos_bool shift_pressed = PYOS_FALSE;
static pyos_bool ctrl_pressed = PYOS_FALSE;
static pyos_bool alt_pressed = PYOS_FALSE;
static keypress_handler_t user_handler = NULL;
static pyos_bool warned_no_handler = PYOS_FALSE;

static const char scancode_map[128] = {
    0, 0, '1','2','3','4','5','6','7','8','9','0','-','=', '\b',
    '\t','q','w','e','r','t','y','u','i','o','p','[',']','\n', 0,
    'a','s','d','f','g','h','j','k','l',';','\'','`', 0, '\\',
    'z','x','c','v','b','n','m',',','.','/', 0, '*', 0, ' ', 0,
};

static const char scancode_map_shift[128] = {
    0, 0, '!','@','#','$','%','^','&','*','(',')','_','+', '\b',
    '\t','Q','W','E','R','T','Y','U','I','O','P','{','}','\n', 0,
    'A','S','D','F','G','H','J','K','L',':','"','~', 0, '|',
    'Z','X','C','V','B','N','M','<','>','?', 0, '*', 0, ' ', 0,
};

static void buffer_push(KeyEvent ev) {
    int next = (buf_tail + 1) % BUF_SIZE;
    if (next == buf_head) return;
    buffer[buf_tail] = ev;
    buf_tail = next;
}

void keyboard_init(void) {
    buf_head = buf_tail = 0;
    shift_pressed = ctrl_pressed = alt_pressed = PYOS_FALSE;
    user_handler = NULL;
    warned_no_handler = PYOS_FALSE;
}

void keyboard_set_handler(keypress_handler_t handler) {
    user_handler = handler;
}

void keyboard_irq_handler(void) {
    u8 scancode = inb(KB_DATA);
    pyos_bool pressed = (scancode & 0x80) == 0;
    u8 code = scancode & 0x7F;

    if (code == 0x2A || code == 0x36) {
        shift_pressed = pressed;
        return;
    }
    if (code == 0x1D) {
        ctrl_pressed = pressed;
        return;
    }
    if (code == 0x38) {
        alt_pressed = pressed;
        return;
    }

    if (!pressed) return;

    KeyEvent ev;
    ev.scancode = code;
    ev.pressed = PYOS_TRUE;
    ev.shift = shift_pressed;
    ev.ctrl = ctrl_pressed;
    ev.alt = alt_pressed;
    if (shift_pressed) {
        ev.ch = (code < 128) ? scancode_map_shift[code] : 0;
    } else {
        ev.ch = (code < 128) ? scancode_map[code] : 0;
    }

    buffer_push(ev);

    if (user_handler) {
        user_handler(&ev);
    } else if (g_kernel_config.has_keypress_handler) {
        pyos_user_keypress(ev.ch, ev.scancode);
    } else if (!warned_no_handler) {
        warned_no_handler = PYOS_TRUE;
        debug_log("IRQ1 keyboard fired but no @kernel.on_keypress handler is registered");
    }
}

pyos_bool keyboard_has_key(void) {
    return buf_head != buf_tail;
}

KeyEvent keyboard_read_key(void) {
    KeyEvent empty = {0, 0, PYOS_FALSE, PYOS_FALSE, PYOS_FALSE, PYOS_FALSE};
    if (buf_head == buf_tail) return empty;
    KeyEvent ev = buffer[buf_head];
    buf_head = (buf_head + 1) % BUF_SIZE;
    return ev;
}

char keyboard_read_char(void) {
    KeyEvent ev = keyboard_read_key();
    return ev.ch;
}
