/* Interrupt stubs — GNU as, preprocessed for Windows/Linux ABI */
.text

#ifdef _WIN32
#define S(name) _##name
#else
#define S(name) name
#endif

.macro ISR_NOERR num
.global S(isr_stub_\num)
S(isr_stub_\num):
    cli
    pushl $0
    pushl $\num
    jmp isr_common
.endm

.macro ISR_ERR num
.global S(isr_stub_\num)
S(isr_stub_\num):
    cli
    pushl $\num
    jmp isr_common
.endm

.macro IRQ_STUB irq, num
.global S(irq_stub_\irq)
S(irq_stub_\irq):
    cli
    pushl $0
    pushl $\num
    jmp irq_common
.endm

ISR_NOERR 0
ISR_NOERR 1
ISR_NOERR 2
ISR_NOERR 3
ISR_NOERR 4
ISR_NOERR 5
ISR_NOERR 6
ISR_NOERR 7
ISR_ERR 8
ISR_NOERR 9
ISR_ERR 10
ISR_ERR 11
ISR_ERR 12
ISR_ERR 13
ISR_ERR 14
ISR_NOERR 15
ISR_NOERR 16
ISR_ERR 17
ISR_NOERR 18
ISR_NOERR 19
ISR_NOERR 20
ISR_NOERR 21
ISR_NOERR 22
ISR_NOERR 23
ISR_NOERR 24
ISR_NOERR 25
ISR_NOERR 26
ISR_NOERR 27
ISR_NOERR 28
ISR_NOERR 29
ISR_NOERR 30
ISR_NOERR 31

IRQ_STUB 0, 0
IRQ_STUB 1, 1
IRQ_STUB 2, 2
IRQ_STUB 3, 3
IRQ_STUB 4, 4
IRQ_STUB 5, 5
IRQ_STUB 6, 6
IRQ_STUB 7, 7
IRQ_STUB 8, 8
IRQ_STUB 9, 9
IRQ_STUB 10, 10
IRQ_STUB 11, 11
IRQ_STUB 12, 12
IRQ_STUB 13, 13
IRQ_STUB 14, 14
IRQ_STUB 15, 15

.global S(isr_stub_128)
S(isr_stub_128):
    cli
    pushl $0
    pushl $0x80
    jmp syscall_common

.extern S(fault_handler)
.extern S(irq_handler)
.extern S(syscall_handler_c)
.extern S(task_save_user_frame)

isr_common:
    pusha
    movl 32(%esp), %eax
    movl 36(%esp), %edx
    movl 40(%esp), %ecx
    pushl %ecx
    pushl %edx
    pushl %eax
    call S(fault_handler)
    addl $12, %esp
    popa
    addl $8, %esp
    sti
    iret

irq_common:
    pusha
    movl 32(%esp), %eax
    pushl %eax
    call S(irq_handler)
    addl $4, %esp
    popa
    addl $8, %esp
    sti
    iret

/*
 * Linux i386 int 0x80 ABI:
 *   eax=num, ebx/ecx/edx/esi/edi/ebp = args 1..6, return in eax.
 *
 * After pusha the stack is:
 *   [esp+0]=edi [esp+4]=esi [esp+8]=ebp [esp+12]=esp
 *   [esp+16]=ebx [esp+20]=edx [esp+24]=ecx [esp+28]=eax
 *   [esp+32]=int_no [esp+36]=err
 *   [esp+40]=eip [esp+44]=cs [esp+48]=eflags
 *   [esp+52]=user_esp [esp+56]=ss   (only if CPL changed)
 *
 * Stash the C return value into the saved-eax slot before popa so userspace
 * sees the result (popa would otherwise restore the pre-syscall eax).
 */
syscall_common:
    pusha
    /* If privilege changed (ring3), save user frame for fork. */
    movl 44(%esp), %eax          /* CS */
    testl $3, %eax
    jz 1f
    movl 40(%esp), %ebx          /* EIP */
    movl 44(%esp), %ecx          /* CS */
    movl 48(%esp), %edx          /* EFLAGS */
    movl 52(%esp), %esi          /* user ESP */
    movl 56(%esp), %edi          /* SS */
    pushl %edi
    pushl %esi
    pushl %edx
    pushl %ecx
    pushl %ebx
    call S(task_save_user_frame)
    addl $20, %esp
1:
    movl 28(%esp), %eax
    movl 16(%esp), %ebx
    movl 24(%esp), %ecx
    movl 20(%esp), %edx
    movl 4(%esp), %esi
    movl 0(%esp), %edi
    movl 8(%esp), %ebp
    pushl %ebp
    pushl %edi
    pushl %esi
    pushl %edx
    pushl %ecx
    pushl %ebx
    pushl %eax
    call S(syscall_handler_c)
    addl $28, %esp
    movl %eax, 28(%esp)
    popa
    addl $8, %esp
    sti
    iret
