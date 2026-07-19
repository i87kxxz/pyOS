/* Kernel thread context switch — GNU as */
.text

#ifdef _WIN32
#define S(name) _##name
#else
#define S(name) name
#endif

/*
 * void task_switch_asm(u32 *old_esp_slot, u32 new_esp, u32 new_cr3);
 *
 * Saves EFLAGS + EBX/ESI/EDI/EBP, stores ESP into *old_esp_slot,
 * loads CR3 and ESP from the next task, restores regs, returns into
 * the next task (or its first entry trampoline).
 */
.global S(task_switch_asm)
S(task_switch_asm):
    movl 4(%esp), %eax
    movl 8(%esp), %ecx
    movl 12(%esp), %edx

    pushfl
    pushl %ebx
    pushl %esi
    pushl %edi
    pushl %ebp
    movl %esp, (%eax)

    /* Only reload CR3 when it changes (avoids needless TLB flush). */
    movl %cr3, %eax
    cmpl %eax, %edx
    je 1f
    movl %edx, %cr3
1:
    movl %ecx, %esp

    popl %ebp
    popl %edi
    popl %esi
    popl %ebx
    popfl
    ret

/*
 * void enter_userspace(u32 eip, u32 esp);
 * Far-returns into ring3 with CS=0x1B SS=0x23. Does not return.
 */
.global S(enter_userspace)
S(enter_userspace):
    movl 4(%esp), %eax   /* eip */
    movl 8(%esp), %ecx   /* user esp */

    movw $0x23, %dx
    movw %dx, %ds
    movw %dx, %es
    movw %dx, %fs
    movw %dx, %gs

    pushl $0x23          /* SS */
    pushl %ecx           /* ESP */
    pushfl
    orl $0x200, (%esp)   /* IF */
    pushl $0x1B          /* CS */
    pushl %eax           /* EIP */
    iret
