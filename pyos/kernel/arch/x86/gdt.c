#include "gdt.h"
#include "types.h"

struct gdt_entry {
    u16 limit_low;
    u16 base_low;
    u8 base_mid;
    u8 access;
    u8 gran;
    u8 base_high;
} __attribute__((packed));

struct gdt_ptr {
    u16 limit;
    u32 base;
} __attribute__((packed));

struct tss_entry {
    u32 prev_tss;
    u32 esp0;
    u32 ss0;
    u32 esp1;
    u32 ss1;
    u32 esp2;
    u32 ss2;
    u32 cr3;
    u32 eip;
    u32 eflags;
    u32 eax, ecx, edx, ebx;
    u32 esp, ebp, esi, edi;
    u32 es, cs, ss, ds, fs, gs;
    u32 ldt;
    u16 trap;
    u16 iomap_base;
} __attribute__((packed));

static struct gdt_entry gdt[6];
static struct gdt_ptr gp;
static struct tss_entry tss;

static void gdt_set(int num, u32 base, u32 limit, u8 access, u8 gran) {
    gdt[num].base_low = (u16)(base & 0xFFFF);
    gdt[num].base_mid = (u8)((base >> 16) & 0xFF);
    gdt[num].base_high = (u8)((base >> 24) & 0xFF);
    gdt[num].limit_low = (u16)(limit & 0xFFFF);
    gdt[num].gran = (u8)((limit >> 16) & 0x0F);
    gdt[num].gran |= (u8)(gran & 0xF0);
    gdt[num].access = access;
}

void tss_set_kernel_stack(u32 esp0) {
    tss.esp0 = esp0;
    tss.ss0 = 0x10;
}

void gdt_init(void) {
    gp.limit = (u16)(sizeof(gdt) - 1);
    gp.base = (u32)&gdt;

    gdt_set(0, 0, 0, 0, 0);
    gdt_set(1, 0, 0xFFFFFFFF, 0x9A, 0xCF);
    gdt_set(2, 0, 0xFFFFFFFF, 0x92, 0xCF);
    gdt_set(3, 0, 0xFFFFFFFF, 0xFA, 0xCF);
    gdt_set(4, 0, 0xFFFFFFFF, 0xF2, 0xCF);

    u32 tss_base = (u32)&tss;
    u32 tss_limit = sizeof(tss) - 1;
    gdt_set(5, tss_base, tss_limit, 0x89, 0x00);
    for (u32 i = 0; i < sizeof(tss); i++) ((u8 *)&tss)[i] = 0;
    tss.ss0 = 0x10;
    tss.esp0 = 0x90000;
    tss.iomap_base = (u16)sizeof(tss);

    __asm__ volatile ("lgdt (%0)" : : "r"(&gp) : "memory");
    {
        u16 sel = 0x28;
        __asm__ volatile ("ltr %0" : : "r"(sel) : "memory");
    }
}
