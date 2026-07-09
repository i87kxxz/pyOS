#ifndef PYOS_TYPES_H
#define PYOS_TYPES_H

typedef unsigned char      u8;
typedef unsigned short     u16;
typedef unsigned int       u32;
typedef unsigned long long u64;
typedef signed char        i8;
typedef signed short       i16;
typedef signed int         i32;
typedef u32                size_t;
typedef u32                uintptr_t;

#ifndef NULL
#define NULL ((void*)0)
#endif

typedef u8 pyos_bool;
#define PYOS_TRUE 1
#define PYOS_FALSE 0

#endif
