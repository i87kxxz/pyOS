#include "usercopy.h"
#include "kernel.h"
#include "paging.h"
#include "task.h"

/* User virtual window used when enable_user_mode is set. */
#define USER_BASE 0x08000000u
#define USER_END  0xC0000000u

static pyos_bool pages_mapped_ok(u32 addr, u32 len) {
    if (!paging_enabled()) return PYOS_TRUE;
    Task *t = task_current();
    u32 pd = t && t->cr3 ? t->cr3 : paging_get_directory();
    if (!pd) return PYOS_FALSE;
    u32 start = addr & ~(PAGE_SIZE - 1);
    u32 end = (addr + len + PAGE_SIZE - 1) & ~(PAGE_SIZE - 1);
    for (u32 v = start; v < end; v += PAGE_SIZE) {
        if (!paging_is_mapped(pd, v)) return PYOS_FALSE;
    }
    return PYOS_TRUE;
}

/* When user_mode is off, treat all kernel addresses as valid (ring0 lab). */
pyos_bool user_range_ok(u32 addr, u32 len) {
    if (len == 0) return PYOS_TRUE;
    if (addr + len < addr) return PYOS_FALSE; /* overflow */
    if (!g_kernel_config.enable_user_mode) {
        return addr != 0;
    }
    if (addr < USER_BASE) return PYOS_FALSE;
    if (addr + len > USER_END) return PYOS_FALSE;
    if (g_kernel_config.enable_paging || paging_enabled()) {
        return pages_mapped_ok(addr, len);
    }
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
