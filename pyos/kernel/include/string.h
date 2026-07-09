#ifndef PYOS_STRING_H
#define PYOS_STRING_H

#include "types.h"

u32 strlen(const char *s);
int strcmp(const char *a, const char *b);
void *memset(void *dst, int c, u32 n);
void *memcpy(void *dst, const void *src, u32 n);
char *strncpy(char *dst, const char *src, u32 n);

#endif
