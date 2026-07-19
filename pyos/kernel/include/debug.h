#ifndef PYOS_DEBUG_H
#define PYOS_DEBUG_H

#include "types.h"

void serial_init(void);
void serial_write(char c);
void serial_write_str(const char *s);
void serial_write_hex(u32 value);
void serial_write_dec(u32 value);
pyos_bool serial_can_read(void);
i32 serial_read(void); /* -1 if empty, else byte 0..255 */

void debug_log(const char *msg);
void debug_logf(const char *prefix, const char *msg);

void pyos_panic(const char *where, const char *reason, const char *hint);
void pyos_panic_at(const char *where, const char *reason, const char *hint, u32 eip);

#define PANIC(where, reason, hint) pyos_panic(where, reason, hint)

#endif
