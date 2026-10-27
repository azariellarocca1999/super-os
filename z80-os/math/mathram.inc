; Math page work RAM (lives in the user-program area of RAM page $81; the math apps own it while they run).
; Floating point value = 6 bytes: +0 exponent (0 = zero, else value = 0.mant * 2^(exp-128)), +1 sign (0/1),
; +2..+5 mantissa, MSB first, normalised (bit 7 of +2 set).  ~9.6 significant digits, range ~1e-38..1e38.
M_BASE   .equ $9E00
fx_a     .equ M_BASE
fx_b     .equ (M_BASE+6)
fx_c     .equ (M_BASE+12)
fx_d     .equ (M_BASE+18)
fx_e     .equ (M_BASE+24)
fx_x     .equ (M_BASE+30)
fx_t     .equ (M_BASE+36)
fx_u     .equ (M_BASE+42)
fx_v     .equ (M_BASE+48)
fx_pq    .equ (M_BASE+54)       ; 8 bytes
fx_i     .equ (M_BASE+62)       ; 4 bytes (MSB first)
fx_ex    .equ (M_BASE+66)       ; 2
fx_err   .equ (M_BASE+68)       ; 0 ok, 1 domain, 2 overflow, 3 divide by zero, 4 syntax
fx_cnt   .equ (M_BASE+69)
fx_ov    .equ (M_BASE+70)
fx_b0    .equ (M_BASE+71)
fx_qr    .equ (M_BASE+72)       ; 4
fx_q     .equ (M_BASE+76)       ; 4
fx_flag  .equ (M_BASE+80)
fx_flag2 .equ (M_BASE+81)
fx_e10   .equ (M_BASE+82)       ; 2
fx_ptr   .equ (M_BASE+84)       ; 2
fx_dig   .equ (M_BASE+86)       ; 12 digits
fx_str   .equ (M_BASE+100)      ; 32 bytes output text
fx_sgn   .equ (M_BASE+132)
fx_angle .equ (M_BASE+133)      ; 0 radians, 1 degrees
fx_ndig  .equ (M_BASE+134)      ; significant digits to print (1..9)
fx_misc  .equ (M_BASE+136)      ; 16 bytes scratch
fx_vars  .equ (M_BASE+160)      ; 27 variables A..Z, ANS (6 bytes each)
fx_vend  .equ (M_BASE+322)
fx_sav   .equ (M_BASE+330)      ; 6
ev_p     .equ (M_BASE+336)      ; expression pointer
ev_sp    .equ (M_BASE+338)      ; stack pointer to unwind to on a syntax error
fx_end   .equ (M_BASE+340)
