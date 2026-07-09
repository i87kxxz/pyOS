#ifndef PYOS_SYSCALL_H
#define PYOS_SYSCALL_H

#include "types.h"

#define SYS_EXIT   1
#define SYS_SPAWN  2
#define SYS_READ   3
#define SYS_WRITE  4
#define SYS_OPEN   5
#define SYS_CLOSE  6
#define SYS_GETPID 20
#define SYS_MALLOC 90
#define SYS_FREE   91
#define SYS_YIELD  158
#define SYS_SLEEP  162
#define SYS_TIME   201

void syscall_init(void);
i32 syscall_dispatch(u32 num, u32 a1, u32 a2, u32 a3);

#endif
