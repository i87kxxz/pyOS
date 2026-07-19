#ifndef PYOS_EXT2_H
#define PYOS_EXT2_H

#include "types.h"

#define EXT2_ROOT_INO 2u
#define EXT2_NAME_LEN 255u

#define EXT2_S_IFDIR 0x4000u
#define EXT2_S_IFREG 0x8000u

typedef struct {
    u32 inode;
    u16 rec_len;
    u8 name_len;
    u8 file_type;
    char name[EXT2_NAME_LEN + 1];
} Ext2Dirent;

pyos_bool ext2_mounted(void);
i32 ext2_mount(void);

/* Resolve absolute or relative path from root; returns inode or 0. */
u32 ext2_lookup(const char *path);

i32 ext2_read_inode_size(u32 ino, u32 *size_out, u16 *mode_out);
i32 ext2_read(u32 ino, u32 offset, void *buf, u32 len);
i32 ext2_write(u32 ino, u32 offset, const void *buf, u32 len);

/* Create regular file (parents must exist). Returns new inode or 0. */
u32 ext2_create(const char *path);

/* Read entire file into heap buffer (*out owned by caller via heap_free). */
i32 ext2_read_all(u32 ino, u8 **out, u32 *size_out);

/*
 * Fill user buffer with Linux i386 struct linux_dirent entries.
 * *offset is directory byte offset (updated). Returns bytes written, 0 at EOF, -1 on error.
 */
i32 ext2_getdents(u32 ino, u32 *offset, void *buf, u32 buflen);

#endif
