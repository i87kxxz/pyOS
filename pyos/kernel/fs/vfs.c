#include "vfs.h"
#include "heap.h"
#include "string.h"
#include "screen.h"
#include "debug.h"
#include "fat12.h"
#include "kernel.h"

static VfsNode nodes[VFS_MAX_FILES];
static i32 fd_table[VFS_MAX_FILES];

void vfs_init(void) {
    for (int i = 0; i < VFS_MAX_FILES; i++) {
        nodes[i].used = PYOS_FALSE;
        nodes[i].data = 0;
        nodes[i].size = 0;
        nodes[i].capacity = 0;
        nodes[i].name[0] = 0;
        fd_table[i] = -1;
    }
}

i32 vfs_create(const char *path, const u8 *data, u32 size) {
    if (!path) return -1;
    for (int i = 0; i < VFS_MAX_FILES; i++) {
        if (!nodes[i].used) {
            strncpy(nodes[i].name, path, VFS_NAME_LEN - 1);
            nodes[i].name[VFS_NAME_LEN - 1] = 0;
            nodes[i].capacity = size ? size : 1;
            nodes[i].data = (u8 *)heap_malloc(nodes[i].capacity);
            if (!nodes[i].data) return -1;
            nodes[i].size = size;
            if (data && size) {
                for (u32 j = 0; j < size; j++) nodes[i].data[j] = data[j];
            }
            nodes[i].used = PYOS_TRUE;
            return i;
        }
    }
    return -1;
}

i32 vfs_open(const char *path) {
    if (!path) return -1;
    /* skip leading slash */
    if (path[0] == '/') path++;
    for (int i = 0; i < VFS_MAX_FILES; i++) {
        if (nodes[i].used && strcmp(nodes[i].name, path) == 0) {
            for (int fd = 0; fd < VFS_MAX_FILES; fd++) {
                if (fd_table[fd] < 0) {
                    fd_table[fd] = i;
                    return fd;
                }
            }
            return -1;
        }
    }
    return -1;
}

i32 vfs_read(i32 fd, void *buf, u32 len) {
    if (fd < 0 || fd >= VFS_MAX_FILES) return -1;
    i32 idx = fd_table[fd];
    if (idx < 0 || !nodes[idx].used) return -1;
    if (len > nodes[idx].size) len = nodes[idx].size;
    u8 *d = (u8 *)buf;
    for (u32 i = 0; i < len; i++) d[i] = nodes[idx].data[i];
    return (i32)len;
}

i32 vfs_write(i32 fd, const void *buf, u32 len) {
    if (fd < 0 || fd >= VFS_MAX_FILES) return -1;
    i32 idx = fd_table[fd];
    if (idx < 0 || !nodes[idx].used) return -1;
    if (len > nodes[idx].capacity) len = nodes[idx].capacity;
    const u8 *s = (const u8 *)buf;
    for (u32 i = 0; i < len; i++) nodes[idx].data[i] = s[i];
    nodes[idx].size = len;
    return (i32)len;
}

i32 vfs_close(i32 fd) {
    if (fd < 0 || fd >= VFS_MAX_FILES) return -1;
    fd_table[fd] = -1;
    return 0;
}

void vfs_list(void (*cb)(const char *name, u32 size)) {
    if (!cb) return;
    for (int i = 0; i < VFS_MAX_FILES; i++) {
        if (nodes[i].used) cb(nodes[i].name, nodes[i].size);
    }
}

void vfs_mount_root(void) {
    debug_log("VFS root mounted (ramfs)");
    /* default motd if empty */
    int any = 0;
    for (int i = 0; i < VFS_MAX_FILES; i++) if (nodes[i].used) any = 1;
    if (!any) {
        const char *motd = "Welcome to pyOS\n";
        vfs_create("motd.txt", (const u8 *)motd, (u32)strlen(motd));
    }
    if (g_kernel_config.enable_filesystem) {
        fat12_load_seeds_into_vfs();
    }
    screen_print_at("vfs: ready", 21, 0, 0x0B);
}
