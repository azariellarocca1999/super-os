; Minimal ti83plus.inc subset (ids verified against spasm-ng inc/ti83plus.inc)
#define bcall(xxxx) rst 28h \ .dw xxxx
_ClrLCDFull .equ $4540
_ClrScrnFull .equ $4546
_GrBufCpy   .equ $486A
_GrBufClr   .equ $4BD0
_HomeUp     .equ $4558
_NewLine    .equ $452E
_PutC       .equ $4504
_PutS       .equ $450A
_DispHL     .equ $4507
_GetCSC     .equ $4018
_GetKey     .equ $4972
_Random     .equ $4B79
_RunIndicOff .equ $4570
userMem     .equ $9D95
plotSScreen .equ $9340
skEnter     .equ 9
skClear     .equ 15
sk2nd       .equ 54
skDown      .equ 1
skLeft      .equ 2
skRight     .equ 3
skUp        .equ 4
