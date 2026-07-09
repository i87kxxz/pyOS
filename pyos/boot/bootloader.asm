; pyOS Bootloader — LBA (int 13h AH=42h), QEMU-friendly
[BITS 16]
[ORG 0x7C00]

KERNEL_OFFSET equ 0x1000
KERNEL_SEGS   equ 0x0000
KERNEL_SECTORS equ 64

start:
    cli
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7C00
    sti

    mov [boot_drive], dl

    mov al, 'B'
    out 0xE9, al

    ; Check extensions
    mov ah, 0x41
    mov bx, 0x55AA
    mov dl, [boot_drive]
    int 0x13
    jc .no_lba
    cmp bx, 0xAA55
    jne .no_lba

    mov al, 'X'
    out 0xE9, al

    ; LBA read: DAP
    mov si, dap
    mov ah, 0x42
    mov dl, [boot_drive]
    int 0x13
    jc .error

    mov al, 'L'
    out 0xE9, al
    jmp .pm

.no_lba:
    ; Fallback CHS: one track from sector 2 (17 sectors)
    mov al, 'C'
    out 0xE9, al
    mov ax, KERNEL_SEGS
    mov es, ax
    mov bx, KERNEL_OFFSET
    mov ah, 0x02
    mov al, 17
    mov ch, 0
    mov cl, 2
    mov dh, 0
    mov dl, [boot_drive]
    int 0x13
    jc .error
    mov al, 'L'
    out 0xE9, al

.pm:
    cli
    in al, 0x92
    or al, 2
    out 0x92, al
    lgdt [gdt_desc]
    mov eax, cr0
    or eax, 1
    mov cr0, eax
    jmp 0x08:pm_start

.error:
    mov al, 'E'
    out 0xE9, al
    jmp $

; Disk Address Packet
align 4
dap:
    db 16
    db 0
    dw KERNEL_SECTORS
    dw KERNEL_OFFSET
    dw KERNEL_SEGS
    dq 1                 ; LBA 1 (sector after MBR)

gdt_start:
    dq 0
gdt_code:
    dw 0xFFFF, 0x0000
    db 0x00, 10011010b, 11001111b, 0x00
gdt_data:
    dw 0xFFFF, 0x0000
    db 0x00, 10010010b, 11001111b, 0x00
gdt_end:
gdt_desc:
    dw gdt_end - gdt_start - 1
    dd gdt_start

[BITS 32]
pm_start:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov fs, ax
    mov gs, ax
    mov ss, ax
    mov esp, 0x90000
    mov al, 'K'
    out 0xE9, al
    call KERNEL_OFFSET
    mov al, 'H'
    out 0xE9, al
    cli
.halt:
    hlt
    jmp .halt

[BITS 16]
boot_drive: db 0

times 510 - ($ - $$) db 0
dw 0xAA55
