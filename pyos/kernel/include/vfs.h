#ifndef PYOS_VFS_H
#define PYOS_VFS_H

#include "types.h"

#define VFS_MAX_FILES 32
#define VFS_NAME_LEN  64
#define VFS_MAX_FDS   16

#define VFS_BACKEND_RAM  0u
#define VFS_BACKEND_EXT2 1u
#define VFS_BACKEND_DEV  2u

#define VFS_DEV_NULL    1u
#define VFS_DEV_ZERO    2u
#define VFS_DEV_CONSOLE 3u
#define VFS_DEV_TTY     4u

typedef struct {
    char name[VFS_NAME_LEN];
    u8 *data;
    u32 size;
    u32 capacity;
    pyos_bool used;
} VfsNode;

typedef struct {
    pyos_bool used;
    u8 backend;   /* VFS_BACKEND_* */
    i32 node;     /* ramfs node index, or -1 */
    u32 ino;      /* ext2 inode or VFS_DEV_* */
    u32 offset;
    u32 flags;
} VfsFd;

void vfs_init(void);
void vfs_mount_root(void);

/* Path open/create — returns fd (>=0) or -1. */
i32 vfs_open(const char *path);
i32 vfs_open_flags(const char *path, u32 flags);
i32 vfs_read(i32 fd, void *buf, u32 len);
i32 vfs_write(i32 fd, const void *buf, u32 len);
i32 vfs_close(i32 fd);

/* Seed / ramfs create (also used by codegen). */
i32 vfs_create(const char *path, const u8 *data, u32 size);

void vfs_list(void (*cb)(const char *name, u32 size));

/*
 * Resolve path for execve/stat:
 *  - returns ramfs node index (>=0) if found in ramfs
 *  - returns -2 - (i32)ino  encoding for ext2 (negative sentinel)
 * Prefer vfs_resolve() for new code.
 */
i32 vfs_lookup(const char *path);

typedef struct {
    pyos_bool found;
    u8 backend;
    i32 ram_idx;
    u32 ino;
    u32 size;
    u16 mode; /* linux-ish: 0040755 / 0100644 */
} VfsPathInfo;

i32 vfs_resolve(const char *path, VfsPathInfo *out);

const u8 *vfs_node_data(i32 idx);
u32 vfs_node_size(i32 idx);
const char *vfs_node_name(i32 idx);

/* Load file bytes for execve (heap buffer — caller must not free while in use). */
i32 vfs_load_file(const char *path, const u8 **data_out, u32 *size_out);

/* Linux getdents on an open directory fd. */
i32 vfs_getdents(i32 fd, void *buf, u32 buflen);

/* Per-task FD table helpers */
void vfs_fd_table_init(VfsFd *fds);
VfsFd *vfs_current_fds(void);

#endif
