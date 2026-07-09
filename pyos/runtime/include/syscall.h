#ifndef PYOS_SYSCALL_H
#define PYOS_SYSCALL_H

#include "types.h"

#define SYS_EXIT  1
#define SYS_READ  3
#define SYS_WRITE 4

void syscall_init(void);
i32 syscall_dispatch(u32 num, u32 a1, u32 a2, u32 a3);

#endif
