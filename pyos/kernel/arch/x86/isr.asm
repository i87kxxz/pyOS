; Interrupt stubs — NASM win32 adds leading underscores automatically
[BITS 32]

%macro ISR_NOERR 1
global isr_stub_%1
isr_stub_%1:
    cli
    push dword 0
    push dword %1
    jmp isr_common
%endmacro

%macro ISR_ERR 1
global isr_stub_%1
isr_stub_%1:
    cli
    push dword %1
    jmp isr_common
%endmacro

%macro IRQ 2
global irq_stub_%1
irq_stub_%1:
    cli
    push dword 0
    push dword %2
    jmp irq_common
%endmacro

ISR_NOERR 0
ISR_NOERR 1
ISR_NOERR 2
ISR_NOERR 3
ISR_NOERR 4
ISR_NOERR 5
ISR_NOERR 6
ISR_NOERR 7
ISR_ERR   8
ISR_NOERR 9
ISR_ERR   10
ISR_ERR   11
ISR_ERR   12
ISR_ERR   13
ISR_ERR   14
ISR_NOERR 15
ISR_NOERR 16
ISR_ERR   17
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

IRQ 0, 0
IRQ 1, 1
IRQ 2, 2
IRQ 3, 3
IRQ 4, 4
IRQ 5, 5
IRQ 6, 6
IRQ 7, 7
IRQ 8, 8
IRQ 9, 9
IRQ 10, 10
IRQ 11, 11
IRQ 12, 12
IRQ 13, 13
IRQ 14, 14
IRQ 15, 15

global isr_stub_128
isr_stub_128:
    cli
    push dword 0
    push dword 0x80
    jmp syscall_common

extern fault_handler
extern irq_handler
extern syscall_handler_c

isr_common:
    pusha
    mov eax, [esp + 32]
    mov edx, [esp + 36]
    mov ecx, [esp + 40]
    push ecx
    push edx
    push eax
    call fault_handler
    add esp, 12
    popa
    add esp, 8
    sti
    iret

irq_common:
    pusha
    mov eax, [esp + 32]
    push eax
    call irq_handler
    add esp, 4
    popa
    add esp, 8
    sti
    iret

; Linux i386 int 0x80: args in ebx,ecx,edx,esi,edi,ebp; return in eax.
; Write C return value into the pusha-saved eax slot before popa.
syscall_common:
    pusha
    mov eax, [esp + 28]
    mov ebx, [esp + 16]
    mov ecx, [esp + 24]
    mov edx, [esp + 20]
    mov esi, [esp + 4]
    mov edi, [esp + 0]
    mov ebp, [esp + 8]
    push ebp
    push edi
    push esi
    push edx
    push ecx
    push ebx
    push eax
    call syscall_handler_c
    add esp, 28
    mov [esp + 28], eax
    popa
    add esp, 8
    sti
    iret
