#ifndef PYOS_ELF_H
#define PYOS_ELF_H

#include "types.h"

#define ELF_MAGIC 0x464C457Fu /* \x7fELF little-endian */
#define ELF_CLASS32 1
#define ELF_DATA_LSB 1
#define ELF_ET_EXEC 2
#define ELF_ET_DYN 3
#define ELF_EM_386 3
#define ELF_PT_LOAD 1
#define ELF_PF_X 1
#define ELF_PF_W 2
#define ELF_PF_R 4

typedef struct {
    u32 magic;
    u8 cls;
    u8 data;
    u8 version;
    u8 osabi;
    u8 abiver;
    u8 pad[7];
    u16 type;
    u16 machine;
    u32 version2;
    u32 entry;
    u32 phoff;
    u32 shoff;
    u32 flags;
    u16 ehsize;
    u16 phentsize;
    u16 phnum;
    u16 shentsize;
    u16 shnum;
    u16 shstrndx;
} __attribute__((packed)) Elf32Ehdr;

typedef struct {
    u32 type;
    u32 offset;
    u32 vaddr;
    u32 paddr;
    u32 filesz;
    u32 memsz;
    u32 flags;
    u32 align;
} __attribute__((packed)) Elf32Phdr;

typedef struct {
    u32 entry;
    u32 brk;          /* end of loaded image (page-aligned), for initial brk */
    u32 load_base;    /* lowest PT_LOAD vaddr */
    u32 load_end;     /* highest PT_LOAD vaddr+memsz */
} ElfLoadInfo;

/* Legacy flat loader (kept for compatibility). */
i32 elf_load_flat(const u8 *image, u32 size, u32 *entry_out);

/* Validate ELF32 i386 headers without mapping. */
i32 elf_validate(const u8 *image, u32 size);

/*
 * Load ELF32 PT_LOAD segments into page directory pd_phys (USER pages).
 * Copies file contents into freshly allocated frames. Fills info on success.
 */
i32 elf_load(const u8 *image, u32 size, u32 pd_phys, ElfLoadInfo *info);

#endif
