#ifndef PYOS_PAGING_H
#define PYOS_PAGING_H

#include "types.h"

void paging_init(void);
u32 paging_get_directory(void);
void paging_map_identity(u32 max_addr);
pyos_bool paging_enabled(void);

#endif
