#include "vfs.h"
#include "heap.h"
#include "string.h"
#include "screen.h"
#include "debug.h"
#include "fat12.h"
#include "kernel.h"
#include "blkdev.h"
#include "ext2.h"
#include "task.h"
#include "keyboard.h"

#define O_RDONLY 0u
#define O_WRONLY 1u
#define O_RDWR   2u
#define O_CREAT  0x40u
#define O_TRUNC  0x200u

static VfsNode nodes[VFS_MAX_FILES];
static VfsFd global_fds[VFS_MAX_FDS];
static u8 *loaded_cache;
static u32 loaded_cache_size;
static char loaded_cache_path[VFS_NAME_LEN];

void vfs_fd_table_init(VfsFd *fds) {
    if (!fds) return;
    for (int i = 0; i < VFS_MAX_FDS; i++) {
        fds[i].used = PYOS_FALSE;
        fds[i].backend = VFS_BACKEND_RAM;
        fds[i].node = -1;
        fds[i].ino = 0;
        fds[i].offset = 0;
        fds[i].flags = 0;
    }
}

VfsFd *vfs_current_fds(void) {
    Task *t = task_current();
    if (t && t->state != TASK_FREE) return t->fds;
    return global_fds;
}

void vfs_init(void) {
    for (int i = 0; i < VFS_MAX_FILES; i++) {
        nodes[i].used = PYOS_FALSE;
        nodes[i].data = 0;
        nodes[i].size = 0;
        nodes[i].capacity = 0;
        nodes[i].name[0] = 0;
    }
    vfs_fd_table_init(global_fds);
    loaded_cache = 0;
    loaded_cache_size = 0;
    loaded_cache_path[0] = 0;
}

static void normalize_path(const char *path, char *out, u32 out_sz) {
    if (!out || out_sz == 0) return;
    out[0] = 0;
    if (!path) return;
    while (*path == '/') path++;
    strncpy(out, path, out_sz - 1);
    out[out_sz - 1] = 0;
}

i32 vfs_create(const char *path, const u8 *data, u32 size) {
    if (!path) return -1;
    char name[VFS_NAME_LEN];
    normalize_path(path, name, sizeof(name));
    if (name[0] == 0) return -1;

    /* Replace existing */
    for (int i = 0; i < VFS_MAX_FILES; i++) {
        if (nodes[i].used && strcmp(nodes[i].name, name) == 0) {
            if (nodes[i].data) heap_free(nodes[i].data);
            nodes[i].capacity = size ? size : 1;
            nodes[i].data = (u8 *)heap_malloc(nodes[i].capacity);
            if (!nodes[i].data) return -1;
            nodes[i].size = size;
            if (data && size) memcpy(nodes[i].data, data, size);
            return i;
        }
    }

    for (int i = 0; i < VFS_MAX_FILES; i++) {
        if (!nodes[i].used) {
            strncpy(nodes[i].name, name, VFS_NAME_LEN - 1);
            nodes[i].name[VFS_NAME_LEN - 1] = 0;
            nodes[i].capacity = size ? size : 1;
            nodes[i].data = (u8 *)heap_malloc(nodes[i].capacity);
            if (!nodes[i].data) return -1;
            nodes[i].size = size;
            if (data && size) memcpy(nodes[i].data, data, size);
            nodes[i].used = PYOS_TRUE;
            return i;
        }
    }
    return -1;
}

i32 vfs_resolve(const char *path, VfsPathInfo *out) {
    if (!out) return -1;
    memset(out, 0, sizeof(*out));
    if (!path) return -1;

    char name[VFS_NAME_LEN];
    normalize_path(path, name, sizeof(name));

    /* Synthetic /dev nodes (prefer over empty ext2 placeholders). */
    if (strcmp(name, "dev/null") == 0 || strcmp(name, "dev\\null") == 0) {
        out->found = PYOS_TRUE;
        out->backend = VFS_BACKEND_DEV;
        out->ino = VFS_DEV_NULL;
        out->mode = 0020666;
        return 0;
    }
    if (strcmp(name, "dev/zero") == 0) {
        out->found = PYOS_TRUE;
        out->backend = VFS_BACKEND_DEV;
        out->ino = VFS_DEV_ZERO;
        out->mode = 0020666;
        return 0;
    }
    if (strcmp(name, "dev/console") == 0 || strcmp(name, "dev/tty") == 0) {
        out->found = PYOS_TRUE;
        out->backend = VFS_BACKEND_DEV;
        out->ino = (strcmp(name, "dev/tty") == 0) ? VFS_DEV_TTY : VFS_DEV_CONSOLE;
        out->mode = 0020666;
        return 0;
    }

    /* Ramfs first (seed ELFs like "hi") */
    if (name[0]) {
        for (int i = 0; i < VFS_MAX_FILES; i++) {
            if (nodes[i].used && strcmp(nodes[i].name, name) == 0) {
                out->found = PYOS_TRUE;
                out->backend = VFS_BACKEND_RAM;
                out->ram_idx = i;
                out->size = nodes[i].size;
                out->mode = 0100644;
                return 0;
            }
        }
    }

    /* Directory "/" */
    if (path[0] == '/' && (path[1] == 0 || name[0] == 0)) {
        out->found = PYOS_TRUE;
        out->backend = ext2_mounted() ? VFS_BACKEND_EXT2 : VFS_BACKEND_RAM;
        out->ino = 2;
        out->mode = 0040755;
        out->size = 0;
        return 0;
    }

    if (ext2_mounted()) {
        u32 ino = ext2_lookup(path);
        if (ino) {
            u32 sz = 0;
            u16 mode = 0;
            if (ext2_read_inode_size(ino, &sz, &mode) != 0) return -1;
            out->found = PYOS_TRUE;
            out->backend = VFS_BACKEND_EXT2;
            out->ino = ino;
            out->size = sz;
            out->mode = mode;
            return 0;
        }
    }

    return -1;
}

i32 vfs_lookup(const char *path) {
    VfsPathInfo info;
    if (vfs_resolve(path, &info) != 0 || !info.found) return -1;
    if (info.backend == VFS_BACKEND_RAM) return info.ram_idx;
    /* Encode ext2 inode as negative sentinel: -2 - ino  (ino>=1 => <= -3) */
    return -2 - (i32)info.ino;
}

const u8 *vfs_node_data(i32 idx) {
    if (idx < 0 || idx >= VFS_MAX_FILES || !nodes[idx].used) return 0;
    return nodes[idx].data;
}

u32 vfs_node_size(i32 idx) {
    if (idx < 0 || idx >= VFS_MAX_FILES || !nodes[idx].used) return 0;
    return nodes[idx].size;
}

const char *vfs_node_name(i32 idx) {
    if (idx < 0 || idx >= VFS_MAX_FILES || !nodes[idx].used) return "";
    return nodes[idx].name;
}

i32 vfs_load_file(const char *path, const u8 **data_out, u32 *size_out) {
    VfsPathInfo info;
    if (vfs_resolve(path, &info) != 0 || !info.found) return -1;
    if (info.backend == VFS_BACKEND_RAM) {
        if (info.ram_idx < 0) return -1;
        *data_out = nodes[info.ram_idx].data;
        if (size_out) *size_out = nodes[info.ram_idx].size;
        return 0;
    }
    /* Cache last ext2 load for execve */
    if (loaded_cache && strcmp(loaded_cache_path, path) == 0) {
        *data_out = loaded_cache;
        if (size_out) *size_out = loaded_cache_size;
        return 0;
    }
    if (loaded_cache) {
        heap_free(loaded_cache);
        loaded_cache = 0;
    }
    u8 *buf = 0;
    u32 sz = 0;
    if (ext2_read_all(info.ino, &buf, &sz) != 0) return -1;
    loaded_cache = buf;
    loaded_cache_size = sz;
    strncpy(loaded_cache_path, path, VFS_NAME_LEN - 1);
    loaded_cache_path[VFS_NAME_LEN - 1] = 0;
    *data_out = buf;
    if (size_out) *size_out = sz;
    return 0;
}

static i32 alloc_fd(VfsFd *table) {
    /* Reserve 0,1,2 for stdin/out/err conceptually — start at 3 */
    for (int fd = 3; fd < VFS_MAX_FDS; fd++) {
        if (!table[fd].used) return fd;
    }
    for (int fd = 0; fd < VFS_MAX_FDS; fd++) {
        if (!table[fd].used) return fd;
    }
    return -1;
}

i32 vfs_open_flags(const char *path, u32 flags) {
    if (!path) return -1;
    VfsFd *table = vfs_current_fds();
    VfsPathInfo info;

    if (vfs_resolve(path, &info) != 0 || !info.found) {
        if ((flags & O_CREAT) && ext2_mounted()) {
            u32 ino = ext2_create(path);
            if (!ino) return -1;
            info.found = PYOS_TRUE;
            info.backend = VFS_BACKEND_EXT2;
            info.ino = ino;
            info.size = 0;
            info.mode = 0100644;
        } else {
            return -1;
        }
    }

    if ((flags & O_TRUNC) && info.backend == VFS_BACKEND_EXT2 && info.ino) {
        /* truncate via write size 0 — set inode size by writing empty */
        /* simple: ignore full truncate for now if size already 0 */
        (void)flags;
    }

    i32 fd = alloc_fd(table);
    if (fd < 0) return -1;
    table[fd].used = PYOS_TRUE;
    table[fd].backend = info.backend;
    table[fd].node = info.ram_idx;
    table[fd].ino = info.ino;
    table[fd].offset = 0;
    table[fd].flags = flags;
    return fd;
}

i32 vfs_open(const char *path) {
    return vfs_open_flags(path, O_RDONLY);
}

i32 vfs_read(i32 fd, void *buf, u32 len) {
    VfsFd *table = vfs_current_fds();
    if (fd < 0 || fd >= VFS_MAX_FDS || !table[fd].used || !buf) return -1;
    VfsFd *f = &table[fd];

    if (f->backend == VFS_BACKEND_DEV) {
        if (f->ino == VFS_DEV_NULL) return 0;
        if (f->ino == VFS_DEV_ZERO) {
            memset(buf, 0, len);
            return (i32)len;
        }
        /* console/tty: non-blocking serial/keyboard */
        if (len == 0) return 0;
        if (serial_can_read()) {
            i32 c = serial_read();
            if (c < 0) return 0;
            ((char *)buf)[0] = (char)c;
            return 1;
        }
        if (keyboard_has_key()) {
            ((char *)buf)[0] = keyboard_read_char();
            return 1;
        }
        return 0;
    }

    if (f->backend == VFS_BACKEND_RAM) {
        if (f->node < 0 || f->node >= VFS_MAX_FILES || !nodes[f->node].used) return -1;
        if (f->offset >= nodes[f->node].size) return 0;
        u32 avail = nodes[f->node].size - f->offset;
        if (len > avail) len = avail;
        memcpy(buf, nodes[f->node].data + f->offset, len);
        f->offset += len;
        return (i32)len;
    }

    i32 n = ext2_read(f->ino, f->offset, buf, len);
    if (n > 0) f->offset += (u32)n;
    return n;
}

i32 vfs_write(i32 fd, const void *buf, u32 len) {
    VfsFd *table = vfs_current_fds();
    if (fd < 0 || fd >= VFS_MAX_FDS || !table[fd].used || !buf) return -1;
    VfsFd *f = &table[fd];

    if (f->backend == VFS_BACKEND_DEV) {
        if (f->ino == VFS_DEV_NULL) return (i32)len;
        if (f->ino == VFS_DEV_ZERO) return (i32)len;
        const char *p = (const char *)buf;
        for (u32 i = 0; i < len; i++) {
            screen_putchar(p[i]);
            serial_write(p[i]);
        }
        return (i32)len;
    }

    if (f->backend == VFS_BACKEND_RAM) {
        if (f->node < 0 || f->node >= VFS_MAX_FILES || !nodes[f->node].used) return -1;
        u32 end = f->offset + len;
        if (end > nodes[f->node].capacity) {
            /* grow */
            u32 cap = end + 64;
            u8 *nd = (u8 *)heap_malloc(cap);
            if (!nd) return -1;
            if (nodes[f->node].data && nodes[f->node].size)
                memcpy(nd, nodes[f->node].data, nodes[f->node].size);
            if (nodes[f->node].data) heap_free(nodes[f->node].data);
            nodes[f->node].data = nd;
            nodes[f->node].capacity = cap;
        }
        memcpy(nodes[f->node].data + f->offset, buf, len);
        f->offset += len;
        if (f->offset > nodes[f->node].size) nodes[f->node].size = f->offset;
        return (i32)len;
    }

    i32 n = ext2_write(f->ino, f->offset, buf, len);
    if (n > 0) f->offset += (u32)n;
    return n;
}

i32 vfs_getdents(i32 fd, void *buf, u32 buflen) {
    VfsFd *table = vfs_current_fds();
    if (fd < 0 || fd >= VFS_MAX_FDS || !table[fd].used || !buf) return -1;
    VfsFd *f = &table[fd];
    if (f->backend != VFS_BACKEND_EXT2 || !f->ino) return -1;
    return ext2_getdents(f->ino, &f->offset, buf, buflen);
}

i32 vfs_close(i32 fd) {
    VfsFd *table = vfs_current_fds();
    if (fd < 0 || fd >= VFS_MAX_FDS || !table[fd].used) return -1;
    table[fd].used = PYOS_FALSE;
    table[fd].node = -1;
    table[fd].ino = 0;
    table[fd].offset = 0;
    return 0;
}

void vfs_list(void (*cb)(const char *name, u32 size)) {
    if (!cb) return;
    for (int i = 0; i < VFS_MAX_FILES; i++) {
        if (nodes[i].used) cb(nodes[i].name, nodes[i].size);
    }
    if (ext2_mounted()) {
        cb("(ext2)/", 0);
        /* Show /etc/motd if present */
        u32 ino = ext2_lookup("/etc/motd");
        if (ino) {
            u32 sz = 0;
            ext2_read_inode_size(ino, &sz, 0);
            cb("etc/motd", sz);
        }
    }
}

#include "debug.h"

void vfs_mount_root(void) {
    debug_log("VFS mounting...");
    blkdev_init();
    if (blkdev_ready() && ext2_mount() == 0) {
        debug_log("VFS root mounted (ext2)");
        screen_print_at("vfs: ext2", 21, 0, 0x0B);

        /* Gate: print /etc/motd to serial */
        u32 ino = ext2_lookup("/etc/motd");
        if (ino) {
            char buf[256];
            i32 n = ext2_read(ino, 0, buf, sizeof(buf) - 1);
            if (n > 0) {
                buf[n] = 0;
                debug_log("motd:");
                for (i32 i = 0; i < n; i++) serial_write(buf[i]);
                if (buf[n - 1] != '\n') serial_write('\n');
            }
        } else {
            debug_log("ext2: /etc/motd missing");
        }
    } else {
        debug_log("VFS root mounted (ramfs)");
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
}
