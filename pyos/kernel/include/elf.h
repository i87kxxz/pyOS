#ifndef PYOS_ELF_H
#define PYOS_ELF_H

#include "types.h"

i32 elf_load_flat(const u8 *image, u32 size, u32 *entry_out);

#endif
