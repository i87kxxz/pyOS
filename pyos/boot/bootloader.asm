; pyOS Bootloader
; Simple bootloader that loads kernel and switches to protected mode

[BITS 16]
[ORG 0x7C00]

KERNEL_OFFSET equ 0x1000

start:
    ; Setup segments
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7C00

    ; Save boot drive
    mov [BOOT_DRIVE], dl

    ; Print message
    mov si, MSG_BOOT
    call print

    ; Load kernel
    call load_kernel

    mov si, MSG_OK
    call print

    ; Go to protected mode
    cli
    
    ; Enable A20
    in al, 0x92
    or al, 2
    out 0x92, al
    
    ; Load GDT
    lgdt [gdt_desc]
    
    ; Enter protected mode
    mov eax, cr0
    or eax, 1
    mov cr0, eax
    
    jmp 0x08:pm_start

;----------------------------------------
; Print (SI = string)
;----------------------------------------
print:
    pusha
.loop:
    lodsb
    test al, al
    jz .done
    mov ah, 0x0E
    int 0x10
    jmp .loop
.done:
    popa
    ret

;----------------------------------------
; Load kernel - read sectors one by one
;----------------------------------------
load_kernel:
    pusha
    
    mov si, MSG_LOAD
    call print
    
    ; Read 16 sectors (8KB) - enough for our kernel
    mov bx, KERNEL_OFFSET   ; Destination
    mov cl, 2               ; Start sector
    mov ch, 0               ; Cylinder
    mov dh, 0               ; Head
    mov dl, [BOOT_DRIVE]
    
    mov al, 16              ; Sectors to read
    
.read:
    mov ah, 0x02            ; Read function
    mov al, 1               ; Read 1 sector at a time
    int 0x13
    jc .error
    
    add bx, 512             ; Next buffer position
    inc cl                  ; Next sector
    cmp cl, 18              ; Sector 18 reached?
    jne .continue
    mov cl, 1               ; Reset to sector 1
    inc dh                  ; Next head
    cmp dh, 2
    jne .continue
    mov dh, 0
    inc ch                  ; Next cylinder
    
.continue:
    cmp bx, KERNEL_OFFSET + (16 * 512)  ; Read 16 sectors?
    jb .read
    
    popa
    ret

.error:
    mov si, MSG_ERR
    call print
    jmp $

;----------------------------------------
; GDT
;----------------------------------------
gdt_start:
    dq 0                    ; Null descriptor

gdt_code:
    dw 0xFFFF               ; Limit
    dw 0x0000               ; Base low
    db 0x00                 ; Base mid
    db 10011010b            ; Access
    db 11001111b            ; Flags + limit high
    db 0x00                 ; Base high

gdt_data:
    dw 0xFFFF
    dw 0x0000
    db 0x00
    db 10010010b
    db 11001111b
    db 0x00
gdt_end:

gdt_desc:
    dw gdt_end - gdt_start - 1
    dd gdt_start

;----------------------------------------
; 32-bit mode
;----------------------------------------
[BITS 32]
pm_start:
    mov ax, 0x10            ; Data segment
    mov ds, ax
    mov es, ax
    mov fs, ax
    mov gs, ax
    mov ss, ax
    mov esp, 0x90000
    
    ; Jump to kernel
    call KERNEL_OFFSET
    
    ; Halt
    cli
.halt:
    hlt
    jmp .halt

;----------------------------------------
; Data
;----------------------------------------
[BITS 16]
BOOT_DRIVE: db 0
MSG_BOOT:   db "pyOS v0.1", 13, 10, 0
MSG_LOAD:   db "Loading...", 13, 10, 0
MSG_OK:     db "OK", 13, 10, 0
MSG_ERR:    db "Disk Error!", 0

;----------------------------------------
; Boot signature
;----------------------------------------
times 510 - ($ - $$) db 0
dw 0xAA55
