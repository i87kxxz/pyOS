#include "floppy.h"

/* In QEMU -fda mode the whole floppy is not identity-mapped at a fixed PA
   for the guest after boot. Seed table is written into the image by the
   builder at FLOPPY_SEED_OFFSET; we expose a static fallback buffer that
   builder-injected runtime can also use via a known low address window.
   For lab builds we place a pointer the VFS can read if the image was
   loaded into RAM by firmware — here we use a linker-visible symbol. */

static u8 seed_fallback[4] = {0, 0, 0, 0};

void floppy_init(void) {}

const u8 *floppy_seed_base(void) {
    /* Prefer in-image offset if identity-mapped (QEMU often maps low mem).
       0x00000000+FLOPPY_SEED_OFFSET is not valid; boot loaded only kernel.
       Seeds are also injected by vfs defaults; return fallback count=0. */
    return seed_fallback;
}
