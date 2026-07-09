#ifndef PYOS_VFS_H
#define PYOS_VFS_H

#include "types.h"

#define VFS_MAX_FILES 16
#define VFS_NAME_LEN  32

typedef struct {
    char name[VFS_NAME_LEN];
    u8 *data;
    u32 size;
    u32 capacity;
    pyos_bool used;
} VfsNode;

void vfs_init(void);
void vfs_mount_root(void);
i32 vfs_open(const char *path);
i32 vfs_read(i32 fd, void *buf, u32 len);
i32 vfs_write(i32 fd, const void *buf, u32 len);
i32 vfs_close(i32 fd);
i32 vfs_create(const char *path, const u8 *data, u32 size);
void vfs_list(void (*cb)(const char *name, u32 size));

#endif
