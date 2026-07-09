#ifndef PYOS_FAT12_H
#define PYOS_FAT12_H

#include "types.h"

void fat12_init(u32 image_lba_offset);
i32 fat12_load_seeds_into_vfs(void);

#endif
