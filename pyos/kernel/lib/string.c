#include "string.h"

u32 strlen(const char *s) {
    u32 n = 0;
    if (!s) return 0;
    while (s[n]) n++;
    return n;
}

int strcmp(const char *a, const char *b) {
    if (!a || !b) return (a == b) ? 0 : (a ? 1 : -1);
    while (*a && *a == *b) { a++; b++; }
    return (int)(u8)*a - (int)(u8)*b;
}

void *memset(void *dst, int c, u32 n) {
    u8 *p = (u8 *)dst;
    for (u32 i = 0; i < n; i++) p[i] = (u8)c;
    return dst;
}

void *memcpy(void *dst, const void *src, u32 n) {
    u8 *d = (u8 *)dst;
    const u8 *s = (const u8 *)src;
    for (u32 i = 0; i < n; i++) d[i] = s[i];
    return dst;
}

char *strncpy(char *dst, const char *src, u32 n) {
    u32 i = 0;
    for (; i < n && src[i]; i++) dst[i] = src[i];
    for (; i < n; i++) dst[i] = 0;
    return dst;
}
