#ifndef PYOS_FLOPPY_H
#define PYOS_FLOPPY_H

#include "types.h"

/* Memory-mapped floppy image access for QEMU -fda (seed region). */
#define FLOPPY_SEED_OFFSET (512u + 64u * 512u)

void floppy_init(void);
const u8 *floppy_seed_base(void);

#endif
