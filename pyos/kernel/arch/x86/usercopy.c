#include "usercopy.h"
#include "kernel.h"

/* When user_mode is off, treat all kernel addresses as valid (ring0 lab). */
pyos_bool user_range_ok(u32 addr, u32 len) {
    if (len == 0) return PYOS_TRUE;
    if (addr + len < addr) return PYOS_FALSE; /* overflow */
    if (!g_kernel_config.enable_user_mode) {
        /* Still reject NULL and VGA-ish accidental? Allow kernel for ring0. */
        return addr != 0;
    }
    /* User space window: 0x08000000 .. 0x0FFFFFFF (example) */
    if (addr < 0x08000000u) return PYOS_FALSE;
    if (addr + len > 0x10000000u) return PYOS_FALSE;
    return PYOS_TRUE;
}

i32 copy_from_user(void *dst, u32 user_src, u32 len) {
    if (!user_range_ok(user_src, len)) return -1;
    u8 *d = (u8 *)dst;
    const u8 *s = (const u8 *)user_src;
    for (u32 i = 0; i < len; i++) d[i] = s[i];
    return 0;
}

i32 copy_to_user(u32 user_dst, const void *src, u32 len) {
    if (!user_range_ok(user_dst, len)) return -1;
    u8 *d = (u8 *)user_dst;
    const u8 *s = (const u8 *)src;
    for (u32 i = 0; i < len; i++) d[i] = s[i];
    return 0;
}
