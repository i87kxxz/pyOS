#include "ext2.h"
#include "blkdev.h"
#include "heap.h"
#include "string.h"
#include "debug.h"

/* Packed on-disk structures (little-endian). */
struct ext2_superblock {
    u32 s_inodes_count;
    u32 s_blocks_count;
    u32 s_r_blocks_count;
    u32 s_free_blocks_count;
    u32 s_free_inodes_count;
    u32 s_first_data_block;
    u32 s_log_block_size;
    u32 s_log_frag_size;
    u32 s_blocks_per_group;
    u32 s_frags_per_group;
    u32 s_inodes_per_group;
    u32 s_mtime;
    u32 s_wtime;
    u16 s_mnt_count;
    u16 s_max_mnt_count;
    u16 s_magic;
    u16 s_state;
    u16 s_errors;
    u16 s_minor_rev_level;
    u32 s_lastcheck;
    u32 s_checkinterval;
    u32 s_creator_os;
    u32 s_rev_level;
    u16 s_def_resuid;
    u16 s_def_resgid;
    u32 s_first_ino;
    u16 s_inode_size;
    u16 s_block_group_nr;
    /* rest unused for our purposes */
} __attribute__((packed));

struct ext2_group_desc {
    u32 bg_block_bitmap;
    u32 bg_inode_bitmap;
    u32 bg_inode_table;
    u16 bg_free_blocks_count;
    u16 bg_free_inodes_count;
    u16 bg_used_dirs_count;
    u16 bg_pad;
    u8 bg_reserved[12];
} __attribute__((packed));

struct ext2_inode {
    u16 i_mode;
    u16 i_uid;
    u32 i_size;
    u32 i_atime;
    u32 i_ctime;
    u32 i_mtime;
    u32 i_dtime;
    u16 i_gid;
    u16 i_links_count;
    u32 i_blocks;
    u32 i_flags;
    u32 i_osd1;
    u32 i_block[15];
    u32 i_generation;
    u32 i_file_acl;
    u32 i_dir_acl;
    u32 i_faddr;
    u8 i_osd2[12];
} __attribute__((packed));

struct ext2_dir_entry {
    u32 inode;
    u16 rec_len;
    u8 name_len;
    u8 file_type;
} __attribute__((packed));

#define EXT2_MAGIC 0xEF53u
#define EXT2_FT_REG 1u
#define EXT2_FT_DIR 2u

static pyos_bool mounted;
static struct ext2_superblock sb;
static struct ext2_group_desc gd;
static u32 block_size;
static u32 inode_size;
static u8 *block_buf; /* scratch block */
static u8 *inode_buf;

static i32 read_sectors_into(u64 sector, void *dst, u32 nsec) {
    return blkdev_read(sector, dst, nsec);
}

static i32 write_sectors_from(u64 sector, const void *src, u32 nsec) {
    return blkdev_write(sector, src, nsec);
}

static i32 read_block(u32 block, void *dst) {
    if (!dst || block_size == 0) return -1;
    u64 byte_off = (u64)block * (u64)block_size;
    u64 sector = byte_off / BLK_SECTOR_SIZE;
    u32 nsec = block_size / BLK_SECTOR_SIZE;
    return read_sectors_into(sector, dst, nsec);
}

static i32 write_block(u32 block, const void *src) {
    if (!src || block_size == 0) return -1;
    u64 byte_off = (u64)block * (u64)block_size;
    u64 sector = byte_off / BLK_SECTOR_SIZE;
    u32 nsec = block_size / BLK_SECTOR_SIZE;
    return write_sectors_from(sector, src, nsec);
}

pyos_bool ext2_mounted(void) {
    return mounted;
}

i32 ext2_mount(void) {
    mounted = PYOS_FALSE;
    if (!blkdev_ready()) return -1;

    /* Superblock at byte 1024 */
    u8 sb_raw[1024];
    if (read_sectors_into(2, sb_raw, 2) != 0) return -1;
    memcpy(&sb, sb_raw, sizeof(sb));
    if (sb.s_magic != EXT2_MAGIC) {
        debug_log("ext2: bad magic");
        return -1;
    }

    block_size = 1024u << sb.s_log_block_size;
    if (block_size != 1024 && block_size != 2048 && block_size != 4096) {
        debug_log("ext2: unsupported block size");
        return -1;
    }
    inode_size = sb.s_inode_size ? sb.s_inode_size : 128;
    if (inode_size < 128) inode_size = 128;

    block_buf = (u8 *)heap_malloc(block_size);
    inode_buf = (u8 *)heap_malloc(inode_size);
    if (!block_buf || !inode_buf) {
        debug_log("ext2: OOM for buffers");
        return -1;
    }

    /* Group descriptor 0: block after superblock */
    u32 gd_block = sb.s_first_data_block + 1;
    if (read_block(gd_block, block_buf) != 0) {
        debug_log("ext2: GD read failed");
        return -1;
    }
    memcpy(&gd, block_buf, sizeof(gd));

    mounted = PYOS_TRUE;
    debug_log("ext2: mounted");
    return 0;
}

static i32 read_inode(u32 ino, struct ext2_inode *out) {
    if (!mounted || ino == 0 || !out) return -1;
    u32 index = ino - 1;
    u32 group = index / sb.s_inodes_per_group;
    (void)group; /* single group for our small images */
    u32 index_in_group = index % sb.s_inodes_per_group;
    u32 inode_table = gd.bg_inode_table;
    u32 byte_off = index_in_group * inode_size;
    u32 block = inode_table + (byte_off / block_size);
    u32 off = byte_off % block_size;

    if (read_block(block, block_buf) != 0) return -1;
    memcpy(out, block_buf + off, sizeof(*out) < inode_size ? sizeof(*out) : inode_size);
    return 0;
}

static i32 write_inode(u32 ino, const struct ext2_inode *in) {
    if (!mounted || ino == 0 || !in) return -1;
    u32 index = ino - 1;
    u32 index_in_group = index % sb.s_inodes_per_group;
    u32 inode_table = gd.bg_inode_table;
    u32 byte_off = index_in_group * inode_size;
    u32 block = inode_table + (byte_off / block_size);
    u32 off = byte_off % block_size;

    if (read_block(block, block_buf) != 0) return -1;
    memcpy(block_buf + off, in, sizeof(*in));
    /* zero pad rest of inode slot if larger */
    if (inode_size > sizeof(*in)) {
        memset(block_buf + off + sizeof(*in), 0, inode_size - sizeof(*in));
    }
    return write_block(block, block_buf);
}

static u32 get_block_number(const struct ext2_inode *ino, u32 logical) {
    if (logical < 12) return ino->i_block[logical];
    /* single indirect */
    if (logical < 12 + (block_size / 4)) {
        u32 ind = ino->i_block[12];
        if (!ind) return 0;
        if (read_block(ind, block_buf) != 0) return 0;
        u32 *ptrs = (u32 *)block_buf;
        return ptrs[logical - 12];
    }
    return 0; /* no double/triple for now */
}

i32 ext2_read_inode_size(u32 ino, u32 *size_out, u16 *mode_out) {
    struct ext2_inode node;
    if (read_inode(ino, &node) != 0) return -1;
    if (size_out) *size_out = node.i_size;
    if (mode_out) *mode_out = node.i_mode;
    return 0;
}

i32 ext2_read(u32 ino, u32 offset, void *buf, u32 len) {
    struct ext2_inode node;
    if (read_inode(ino, &node) != 0 || !buf) return -1;
    if (offset >= node.i_size) return 0;
    if (offset + len > node.i_size) len = node.i_size - offset;

    u8 *dst = (u8 *)buf;
    u32 done = 0;
    while (done < len) {
        u32 file_off = offset + done;
        u32 logical = file_off / block_size;
        u32 b_off = file_off % block_size;
        u32 chunk = block_size - b_off;
        if (chunk > len - done) chunk = len - done;

        u32 phys = get_block_number(&node, logical);
        if (!phys) {
            memset(dst + done, 0, chunk);
        } else {
            if (read_block(phys, block_buf) != 0) return -1;
            memcpy(dst + done, block_buf + b_off, chunk);
        }
        done += chunk;
    }
    return (i32)done;
}

i32 ext2_read_all(u32 ino, u8 **out, u32 *size_out) {
    u32 size = 0;
    if (ext2_read_inode_size(ino, &size, 0) != 0) return -1;
    u8 *buf = (u8 *)heap_malloc(size ? size : 1);
    if (!buf) return -1;
    if (size && ext2_read(ino, 0, buf, size) != (i32)size) {
        heap_free(buf);
        return -1;
    }
    *out = buf;
    if (size_out) *size_out = size;
    return 0;
}

static i32 name_eq(const char *a, u8 alen, const char *b) {
    u32 blen = strlen(b);
    if (alen != blen) return 0;
    for (u8 i = 0; i < alen; i++) if (a[i] != b[i]) return 0;
    return 1;
}

static u32 dir_lookup(u32 dir_ino, const char *name) {
    struct ext2_inode node;
    if (read_inode(dir_ino, &node) != 0) return 0;
    if ((node.i_mode & 0xF000u) != EXT2_S_IFDIR) return 0;

    u32 pos = 0;
    while (pos < node.i_size) {
        u32 logical = pos / block_size;
        u32 b_off = pos % block_size;
        u32 phys = get_block_number(&node, logical);
        if (!phys) break;
        if (read_block(phys, block_buf) != 0) break;

        while (b_off + 8 <= block_size && pos < node.i_size) {
            struct ext2_dir_entry *de = (struct ext2_dir_entry *)(block_buf + b_off);
            if (de->rec_len < 8) return 0;
            if (de->inode && de->name_len) {
                const char *n = (const char *)(block_buf + b_off + 8);
                if (name_eq(n, de->name_len, name)) return de->inode;
            }
            b_off += de->rec_len;
            pos += de->rec_len;
            if (b_off >= block_size) break;
        }
        if (b_off >= block_size) {
            /* continue next block — pos already advanced */
        }
    }
    return 0;
}

u32 ext2_lookup(const char *path) {
    if (!mounted || !path) return 0;
    while (*path == '/') path++;
    if (*path == 0) return EXT2_ROOT_INO;

    u32 cur = EXT2_ROOT_INO;
    char comp[64];
    while (*path) {
        u32 i = 0;
        while (*path && *path != '/' && i + 1 < sizeof(comp)) {
            comp[i++] = *path++;
        }
        comp[i] = 0;
        while (*path == '/') path++;
        if (i == 0) continue;
        u32 next = dir_lookup(cur, comp);
        if (!next) return 0;
        cur = next;
    }
    return cur;
}

/* --- allocation helpers (single block group) --- */

static i32 bitmap_find_and_set(u32 bitmap_block, u32 count, u32 *out_bit) {
    if (read_block(bitmap_block, block_buf) != 0) return -1;
    for (u32 bit = 0; bit < count; bit++) {
        u32 byte = bit / 8;
        u8 mask = (u8)(1u << (bit % 8));
        if ((block_buf[byte] & mask) == 0) {
            block_buf[byte] |= mask;
            if (write_block(bitmap_block, block_buf) != 0) return -1;
            *out_bit = bit;
            return 0;
        }
    }
    return -1;
}

static u32 alloc_block(void) {
    u32 bit = 0;
    if (bitmap_find_and_set(gd.bg_block_bitmap, sb.s_blocks_per_group, &bit) != 0)
        return 0;
    u32 block = sb.s_first_data_block + bit;
    /* clear new block */
    memset(block_buf, 0, block_size);
    write_block(block, block_buf);
    if (gd.bg_free_blocks_count) gd.bg_free_blocks_count--;
    if (sb.s_free_blocks_count) sb.s_free_blocks_count--;
    /* write back GD + SB (best-effort) */
    {
        u32 gd_block = sb.s_first_data_block + 1;
        u8 tmp[1024];
        if (read_block(gd_block, tmp) == 0) {
            memcpy(tmp, &gd, sizeof(gd));
            write_block(gd_block, tmp);
        }
    }
    return block;
}

static u32 alloc_inode(void) {
    u32 bit = 0;
    if (bitmap_find_and_set(gd.bg_inode_bitmap, sb.s_inodes_per_group, &bit) != 0)
        return 0;
    u32 ino = bit + 1;
    if (gd.bg_free_inodes_count) gd.bg_free_inodes_count--;
    if (sb.s_free_inodes_count) sb.s_free_inodes_count--;
    return ino;
}

static i32 set_block_number(struct ext2_inode *ino, u32 logical, u32 phys) {
    if (logical < 12) {
        ino->i_block[logical] = phys;
        return 0;
    }
    if (logical < 12 + (block_size / 4)) {
        if (!ino->i_block[12]) {
            u32 ind = alloc_block();
            if (!ind) return -1;
            ino->i_block[12] = ind;
            ino->i_blocks += block_size / 512;
        }
        if (read_block(ino->i_block[12], block_buf) != 0) return -1;
        u32 *ptrs = (u32 *)block_buf;
        ptrs[logical - 12] = phys;
        return write_block(ino->i_block[12], block_buf);
    }
    return -1;
}

i32 ext2_write(u32 ino, u32 offset, const void *buf, u32 len) {
    struct ext2_inode node;
    if (read_inode(ino, &node) != 0 || !buf) return -1;
    if ((node.i_mode & 0xF000u) != EXT2_S_IFREG) return -1;

    const u8 *src = (const u8 *)buf;
    u32 done = 0;
    while (done < len) {
        u32 file_off = offset + done;
        u32 logical = file_off / block_size;
        u32 b_off = file_off % block_size;
        u32 chunk = block_size - b_off;
        if (chunk > len - done) chunk = len - done;

        u32 phys = get_block_number(&node, logical);
        if (!phys) {
            phys = alloc_block();
            if (!phys) return -1;
            if (set_block_number(&node, logical, phys) != 0) return -1;
            node.i_blocks += block_size / 512;
            memset(block_buf, 0, block_size);
        } else {
            if (read_block(phys, block_buf) != 0) return -1;
        }
        memcpy(block_buf + b_off, src + done, chunk);
        if (write_block(phys, block_buf) != 0) return -1;
        done += chunk;
    }

    u32 new_size = offset + len;
    if (new_size > node.i_size) node.i_size = new_size;
    if (write_inode(ino, &node) != 0) return -1;
    return (i32)done;
}

static i32 dir_add_entry(u32 dir_ino, u32 child_ino, const char *name, u8 ftype) {
    struct ext2_inode dir;
    if (read_inode(dir_ino, &dir) != 0) return -1;
    u32 namelen = strlen(name);
    if (namelen == 0 || namelen > 255) return -1;
    u32 need = (u32)(8 + namelen);
    need = (need + 3u) & ~3u;

    u32 pos = 0;
    while (pos < dir.i_size) {
        u32 logical = pos / block_size;
        u32 phys = get_block_number(&dir, logical);
        if (!phys) return -1;
        if (read_block(phys, block_buf) != 0) return -1;

        u32 b_off = 0;
        while (b_off + 8 <= block_size) {
            struct ext2_dir_entry *de = (struct ext2_dir_entry *)(block_buf + b_off);
            if (de->rec_len < 8) return -1;
            u32 ideal = 0;
            if (de->inode) {
                ideal = (u32)(8 + de->name_len);
                ideal = (ideal + 3u) & ~3u;
            }
            if (de->rec_len >= ideal + need && de->inode) {
                u16 old = de->rec_len;
                de->rec_len = (u16)ideal;
                struct ext2_dir_entry *ne =
                    (struct ext2_dir_entry *)(block_buf + b_off + ideal);
                ne->inode = child_ino;
                ne->rec_len = (u16)(old - ideal);
                ne->name_len = (u8)namelen;
                ne->file_type = ftype;
                memcpy((u8 *)ne + 8, name, namelen);
                if (write_block(phys, block_buf) != 0) return -1;
                return 0;
            }
            if (de->inode == 0 && de->rec_len >= need) {
                de->inode = child_ino;
                de->name_len = (u8)namelen;
                de->file_type = ftype;
                memcpy((u8 *)de + 8, name, namelen);
                if (write_block(phys, block_buf) != 0) return -1;
                return 0;
            }
            if (b_off + de->rec_len > block_size) break;
            if (b_off + de->rec_len == block_size ||
                b_off + de->rec_len >= block_size) {
                /* try expand: if this is last entry, shrink and append */
                if (b_off + de->rec_len >= block_size) {
                    u32 ideal2 = de->inode ? ((8u + de->name_len + 3u) & ~3u) : 0;
                    if (de->inode && ideal2 + need <= de->rec_len) {
                        u16 old = de->rec_len;
                        de->rec_len = (u16)ideal2;
                        struct ext2_dir_entry *ne =
                            (struct ext2_dir_entry *)(block_buf + b_off + ideal2);
                        ne->inode = child_ino;
                        ne->rec_len = (u16)(old - ideal2);
                        ne->name_len = (u8)namelen;
                        ne->file_type = ftype;
                        memcpy((u8 *)ne + 8, name, namelen);
                        if (write_block(phys, block_buf) != 0) return -1;
                        return 0;
                    }
                }
                break;
            }
            b_off += de->rec_len;
        }
        pos = (logical + 1) * block_size;
    }

    /* Allocate new directory block */
    u32 logical = dir.i_size / block_size;
    u32 phys = alloc_block();
    if (!phys) return -1;
    if (set_block_number(&dir, logical, phys) != 0) return -1;
    dir.i_blocks += block_size / 512;
    memset(block_buf, 0, block_size);
    struct ext2_dir_entry *ne = (struct ext2_dir_entry *)block_buf;
    ne->inode = child_ino;
    ne->rec_len = (u16)block_size;
    ne->name_len = (u8)namelen;
    ne->file_type = ftype;
    memcpy((u8 *)ne + 8, name, namelen);
    if (write_block(phys, block_buf) != 0) return -1;
    dir.i_size += block_size;
    return write_inode(dir_ino, &dir);
}

u32 ext2_create(const char *path) {
    if (!mounted || !path) return 0;
    while (*path == '/') path++;
    if (*path == 0) return 0;

    /* Split parent / basename */
    char parent[128];
    char base[64];
    u32 plen = strlen(path);
    i32 slash = -1;
    for (u32 i = 0; i < plen; i++) if (path[i] == '/') slash = (i32)i;
    if (slash < 0) {
        parent[0] = 0;
        strncpy(base, path, sizeof(base) - 1);
        base[sizeof(base) - 1] = 0;
    } else {
        u32 n = (u32)slash;
        if (n >= sizeof(parent)) n = sizeof(parent) - 1;
        memcpy(parent, path, n);
        parent[n] = 0;
        strncpy(base, path + slash + 1, sizeof(base) - 1);
        base[sizeof(base) - 1] = 0;
    }
    if (base[0] == 0) return 0;

    u32 dir_ino = parent[0] ? ext2_lookup(parent) : EXT2_ROOT_INO;
    if (!dir_ino) return 0;
    if (dir_lookup(dir_ino, base)) return 0; /* exists */

    u32 ino = alloc_inode();
    if (!ino) return 0;

    struct ext2_inode node;
    memset(&node, 0, sizeof(node));
    node.i_mode = (u16)(EXT2_S_IFREG | 0644);
    node.i_links_count = 1;
    node.i_size = 0;
    if (write_inode(ino, &node) != 0) return 0;
    if (dir_add_entry(dir_ino, ino, base, EXT2_FT_REG) != 0) return 0;
    return ino;
}

/* Linux i386 dirent (getdents) — not getdents64. */
struct linux_dirent {
    u32 d_ino;
    u32 d_off;
    u16 d_reclen;
    char d_name[];
} __attribute__((packed));

i32 ext2_getdents(u32 ino, u32 *offset, void *buf, u32 buflen) {
    struct ext2_inode node;
    if (!offset || !buf || buflen < 16) return -1;
    if (read_inode(ino, &node) != 0) return -1;
    if ((node.i_mode & 0xF000u) != EXT2_S_IFDIR) return -1;

    u8 *dst = (u8 *)buf;
    u32 written = 0;
    u32 pos = *offset;

    while (pos < node.i_size) {
        u32 logical = pos / block_size;
        u32 b_off = pos % block_size;
        u32 phys = get_block_number(&node, logical);
        if (!phys) break;
        if (read_block(phys, block_buf) != 0) return -1;

        while (b_off + 8 <= block_size && pos < node.i_size) {
            struct ext2_dir_entry *de = (struct ext2_dir_entry *)(block_buf + b_off);
            if (de->rec_len < 8) return (i32)written;
            if (de->inode && de->name_len) {
                u32 namelen = de->name_len;
                u32 reclen = (u32)(8 + namelen + 1);
                reclen = (reclen + 3u) & ~3u;
                if (written + reclen > buflen) {
                    *offset = pos;
                    return written ? (i32)written : -1;
                }
                struct linux_dirent *out = (struct linux_dirent *)(dst + written);
                out->d_ino = de->inode;
                out->d_off = pos + de->rec_len;
                out->d_reclen = (u16)reclen;
                memcpy(out->d_name, (const char *)(block_buf + b_off + 8), namelen);
                out->d_name[namelen] = 0;
                written += reclen;
            }
            b_off += de->rec_len;
            pos += de->rec_len;
            if (b_off >= block_size) break;
        }
    }
    *offset = pos;
    return (i32)written;
}
