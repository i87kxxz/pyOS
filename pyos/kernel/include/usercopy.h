#ifndef PYOS_USERCOPY_H
#define PYOS_USERCOPY_H

#include "types.h"

pyos_bool user_range_ok(u32 addr, u32 len);
i32 copy_from_user(void *dst, u32 user_src, u32 len);
i32 copy_to_user(u32 user_dst, const void *src, u32 len);

#endif
