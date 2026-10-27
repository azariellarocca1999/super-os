; =============================================================================
; Super-OS  --  global equates for the TI-83 Plus Silver Edition
;   Z80 @ 15 MHz, 128 KB RAM (8 x 16 KB), 2 MB flash (128 x 16 KB), T6A04 LCD 96x64
; Port facts: WikiTI captures in docs/wikiti + Tilem2 core (see docs/PORTS.md).
; NOTE (spasm-ng): expressions are evaluated LEFT-TO-RIGHT -- always parenthesize a+(b*c).
; =============================================================================

; ---- ports ---------------------------------------------------------------------
P_LINK      .equ $00
P_KEYS      .equ $01
P_STATUS    .equ $02        ; r: b0 battery ok, b1 LCD ready(15MHz), b2 flash unlocked, b7 SE/84+ ; w: ack ints (0 = ack)
P_INTMASK   .equ $03        ; b0 ON, b1 timer1, b2 timer2, b3 =0 low-power on HALT, b4 link
P_MEMMAP    .equ $04        ; r: int source ; w: map mode, timer speed (b1-2), battery threshold (b7)
P_RAMPAGE   .equ $05        ; RAM page 0-7 at $C000
P_BANKA     .equ $06        ; page at $4000 (b7 = RAM)
P_BANKB     .equ $07        ; page at $8000 (b7 = RAM)
P_LCDCMD    .equ $10
P_LCDDATA   .equ $11
P_FLASHLOCK .equ $14
P_SPEED     .equ $20        ; 0 = 6 MHz, 1 = 15 MHz
P_CT1_FREQ  .equ $30        ; crystal timers: on/off+divisor, loop control, counter
P_CT1_LOOP  .equ $31
P_CT1_CNT   .equ $32

INT_RUN     .equ %00011011  ; ON + timer1 + link-activity, powered
INT_RUN_NL  .equ %00001011  ; link irq masked while the link task drains it
INT_SLEEP   .equ %00010001  ; ON + link, LOW POWER on HALT (timers off)
TMR_SLOW    .equ $06        ; legacy timer 1 slowest: 32768/304 = 107.8 Hz
TICK_HZ     .equ 108

LCD_8BIT    .equ $01
LCD_OFF     .equ $02
LCD_ON      .equ $03
LCD_XINC    .equ $05
LCD_COL     .equ $20
LCD_ROW     .equ $80
LCD_CONTR   .equ $C0

; ---- flash pages (SE: 128 x 16 KB) -------------------------------------------------
UI_ENTRY    .equ $4000
PG_KERNEL   .equ $00
PG_UI       .equ $01
PG_ASSETS   .equ $02
PG_SET      .equ $70        ; settings journal (sector $70-$73)
PG_PKGDIR   .equ $20        ; package directory sector ($20-$23)
PG_PKGDATA  .equ $24        ; package data: pages $24-$6F
PG_PKGEND   .equ $6F
PG_SCRATCH  .equ $74        ; diagnostics scratch sector ($74-$77)
PG_PRIV     .equ $7C        ; privileged page: flash unlock routine ($7FF0)
PG_CERT     .equ $7E        ; certificate  -- never writable
PG_BOOT     .equ $7F        ; factory boot -- never writable
RAM_BASE    .equ $80        ; RAM pages $80-$87

; ---- memory map -----------------------------------------------------------------------
; $0000 page 0 kernel | $4000 bank A (UI / app pages) | $8000 RAM $81 (fixed: data+stacks, executable)
; $C000 window = port 5 page ($80-$87): buffers, apps and emulator memory
GBUF1       .equ $8000      ; 768 B frame buffer (plane H in gray mode)
GBUF2       .equ $8300      ; 768 B plane L
VARS        .equ $8600      ; kernel variables (256 B)
SETTINGS    .equ $8700      ; persistent settings (64 B)
TCB         .equ $8800      ; 6 task control blocks x 32 B
FONT3       .equ $8900      ; 3x5 font  (64 glyphs x 5 B = 320)
FONT5       .equ $8A40      ; 5x7 font  (64 glyphs x 7 B = 448)
ICONS       .equ $8C00      ; icons 16x16 (16 x 32 B = 512) -> $8DFF
FSTAB_RAM   .equ $8E00      ; file table copy (16 x 16 B)
FLASHRAM    .equ $8F00      ; flash programming stub (<= 256 B, checked in storage.z80)
NETBUF      .equ $9000      ; 300 B frame buffer
INBUF       .equ $9140      ; text input (96 B)
PLOTSSCREEN .equ $9340      ; TI-OS compatible frame buffer
USERMEM     .equ $9D95      ; TI-OS compatible program load address
TASKSTK     .equ $B000      ; task stacks: slot n occupies $B000+(n*$100)+$FF downwards
BIGSTK      .equ $B800      ; (reserved)
SYSSTK      .equ $BFFF      ; boot/idle stack top

; window $C000 default page contents
RESPBUF     .equ $C000      ; compressed network reply (to $CFFF)
TEXTBUF     .equ $D000      ; decompressed text (to $E7FF)
LINETAB     .equ $E800      ; wrapped-line table
DICTBUF     .equ $F400      ; T9 dictionary (to $FBFF)

; ---- kernel variables (VARS) -------------------------------------------------------------
v_tick      .equ VARS+$00   ; 16-bit, 108 Hz
v_halfs     .equ VARS+$02   ; crystal timer half... counts seconds? (see rtc)
v_sec       .equ VARS+$04   ; 32-bit seconds since 2000-01-01 00:00 (set by NTP) / since boot
v_flags     .equ VARS+$08
v_idle      .equ VARS+$09   ; seconds without input
v_cur       .equ VARS+$0A   ; current task id
v_runmask   .equ VARS+$0B
v_key       .equ VARS+$0C
v_keyrep    .equ VARS+$0D
v_contrast  .equ VARS+$0E
v_mode      .equ VARS+$0F   ; 0 = static (poll keys every 3 ticks), 1 = animated
v_invert    .equ VARS+$10   ; text inverse mask ($00 / $F0 for 4x6, $FF for 5x7)
v_batlvl    .equ VARS+$11   ; 0 low .. 3 full
v_minutes   .equ VARS+$12
v_halts     .equ VARS+$13   ; 16-bit
v_sleeps    .equ VARS+$15   ; 16-bit
v_quantum   .equ VARS+$17
v_evflags   .equ VARS+$18   ; 16-bit event flags
v_nextwake  .equ VARS+$1A
v_font      .equ VARS+$1C   ; 0 = 4x6 (24 cols), 1 = 6x8 (16 cols)
v_statbar   .equ VARS+$1D   ; 1 = status bar visible
v_esp       .equ VARS+$1E   ; 0 ZZZ, 1 ESP awake, 2 WiFi
v_rssi      .equ VARS+$1F
v_halfsec   .equ VARS+$20
v_pcount    .equ VARS+$21
v_savebank  .equ VARS+$22
v_ftest     .equ VARS+$23
v_clockmin  .equ VARS+$24   ; minutes since midnight (derived)
v_resched   .equ VARS+$2A
v_mind      .equ VARS+$2C
v_lnkreq    .equ VARS+$30   ; link mailbox
v_lnklen    .equ VARS+$31
v_lnkptr    .equ VARS+$32
v_lnkstat   .equ VARS+$34
v_lnkresp   .equ VARS+$35   ; 16-bit reply length
v_lnkseq    .equ VARS+$37
v_crc       .equ VARS+$38
v_ptype     .equ VARS+$39
v_plen      .equ VARS+$3A   ; 16-bit
v_netto     .equ VARS+$3C
v_notif     .equ VARS+$3E
v_lnkabort  .equ VARS+$3F   ; 1 = the caller pressed CLEAR while waiting: the link task gives up at its next poll
; GUI / apps scratch
v_sel       .equ VARS+$40
v_tab       .equ VARS+$41
v_row       .equ VARS+$42
v_inlen     .equ VARS+$43
v_t9len     .equ VARS+$44
v_t9sel     .equ VARS+$45
v_t9cnt     .equ VARS+$46
v_dictok    .equ VARS+$47
v_vline     .equ VARS+$48
v_vcount    .equ VARS+$4A
v_vend      .equ VARS+$4C
v_qtype     .equ VARS+$4E
v_pass      .equ VARS+$4F
v_cptr      .equ VARS+$50
v_dllen     .equ VARS+$52
v_str       .equ VARS+$54   ; current language string table pointer
T9SEQ       .equ VARS+$60   ; 12 B
T9CAND0     .equ VARS+$70   ; 3 pointers
v_espidle   .equ VARS+$5E   ; 16-bit seconds since the last ESP32 traffic
v_curcol    .equ VARS+$58
v_currow    .equ VARS+$59
v_bunk      .equ VARS+$56   ; 16-bit: unsupported B_CALLs hit
v_blast     .equ VARS+$62   ; 16-bit: last unsupported id
v_bjmp      .equ VARS+$64   ; 3-byte RAM trampoline
v_clkh      .equ VARS+$5A
v_clkm      .equ VARS+$5B
v_clks      .equ VARS+$5C
v_wcols     .equ VARS+$68
v_model     .equ VARS+$69   ; 0 = deepseek-chat, 1 = deepseek-reasoner
v_edmode    .equ VARS+$6A   ; 0 T9, 1 ABC, 2 123
v_edcase    .equ VARS+$6B   ; 1 = upper case in ABC mode
v_edflags   .equ VARS+$6C   ; b0 = MODE toggles the model
v_nvis      .equ VARS+$6D
v_wptr      .equ VARS+$7A   ; 16-bit
NUMBUF      .equ VARS+$80   ; 8 B
WIFIBUF     .equ PLOTSSCREEN  ; scratch for wifi credentials (free while no TI program runs)
EDBUF       .equ INBUF+1      ; text typed by the user (INBUF holds the model byte)
CMD_API_SET .equ $14
CMD_WEATHER .equ $06
; per-task scratch block, swapped on every context switch (16 B)
SCRATCH     .equ VARS+$F0
v_tmp0      .equ SCRATCH+0
v_tmp1      .equ SCRATCH+1
v_tmp2      .equ SCRATCH+2
v_tmp3      .equ SCRATCH+3
v_dchars    .equ SCRATCH+4
v_graysub   .equ SCRATCH+5
v_gx        .equ SCRATCH+6   ; 16-bit
v_gw        .equ SCRATCH+8   ; 16-bit
v_ui0       .equ SCRATCH+10   ; UI scratch (never touched by kernel/gfx routines)
v_ui1       .equ SCRATCH+11
v_ui2       .equ SCRATCH+12
v_ui3       .equ SCRATCH+13
SCRATCH_LEN .equ 16

; flag bits (v_flags)
F_WANTSLEEP .equ 0
F_ONKEY     .equ 1
F_LINK      .equ 2
F_LOWBAT    .equ 3
F_RTCTICK   .equ 4
F_WOKELINK  .equ 5
F_CDIRTY    .equ 6              ; the contrast shortcut changed the trim: save it on the next other key
F_LOCKREQ   .equ 7              ; the calculator just woke up: the launcher asks for the PIN when the lock is on

; event flags (v_evflags)
EV_LINK     .equ $0001
EV_LNKREQ   .equ $0002
EV_LNKDONE  .equ $0004
EV_ON       .equ $0008
EV_SEC      .equ $0010

; tasks
T_IDLE      .equ 0
T_UI        .equ 1
T_POWER     .equ 2
T_LINK      .equ 3
NTASKS      .equ 6
TCB_SIZE    .equ 32
; TCB: +0 sp(2) +2 wake(2) +4 state +5 evmask(2) +8.. scratch(16)
ST_FREE     .equ 0
ST_READY    .equ 1
ST_SLEEP    .equ 2
ST_WAIT     .equ 3
QUANTUM     .equ 3

; ---- settings --------------------------------------------------------------------------------
s_magic     .equ SETTINGS+0 ; 'S','O'
s_profile   .equ SETTINGS+2 ; 0 alkaline AAA, 1 NiMH, 2 Li-ion/LiPo
s_cadj      .equ SETTINGS+3 ; contrast trim 0..15 (8 neutral)
s_sleepto   .equ SETTINGS+4 ; seconds of inactivity before deep sleep
s_lang      .equ SETTINGS+5 ; 0 ES, 1 EN
s_font      .equ SETTINGS+6 ; default font
s_espsleep  .equ SETTINGS+7 ; ESP32 idle sleep timeout in 10 s units (18 = 180 s)
s_hisc      .equ SETTINGS+8 ; 10 x 16-bit best scores of the native games (journalled with the rest)
s_pin       .equ SETTINGS+28 ; 16-bit: four BCD digits of the lock PIN
s_lock      .equ SETTINGS+30 ; 0 off, 1 PIN after sleep / boot, 2 exam mode (PIN + games, AI and network apps closed)
s_sum       .equ SETTINGS+31
SETTINGS_LEN .equ 32            ; the journal record is 64 B: marker + 32 + checksum + padding

; ---- keyboard codes: row*8 + bit + 1 (identical to TI GetCSC) ------------------------------------
K_NONE      .equ 0
K_DOWN      .equ 1
K_LEFT      .equ 2
K_RIGHT     .equ 3
K_UP        .equ 4
K_ENTER     .equ 9
K_PLUS      .equ 10
K_MINUS     .equ 11
K_MUL       .equ 12
K_DIV       .equ 13
K_POW       .equ 14
K_CLEAR     .equ 15
K_NEG       .equ 17
K_3         .equ 18
K_6         .equ 19
K_9         .equ 20
K_RPAR      .equ 21
K_TAN       .equ 22
K_VARS      .equ 23
K_DOT       .equ 25
K_2         .equ 26
K_5         .equ 27
K_8         .equ 28
K_LPAR      .equ 29
K_COS       .equ 30
K_PRGM      .equ 31
K_STAT      .equ 32
K_0         .equ 33
K_1         .equ 34
K_4         .equ 35
K_7         .equ 36
K_COMMA     .equ 37
K_SIN       .equ 38
K_APPS      .equ 39
K_X         .equ 40
K_STO       .equ 42
K_LN        .equ 43
K_LOG       .equ 44
K_SQ        .equ 45
K_INV       .equ 46
K_MATH      .equ 47
K_ALPHA     .equ 48
K_GRAPH     .equ 49
K_TRACE     .equ 50
K_ZOOM      .equ 51
K_WINDOW    .equ 52
K_YEQ       .equ 53
K_2ND       .equ 54
K_MODE      .equ 55
K_DEL       .equ 56
K_ON        .equ 64

; ---- SuperLink --------------------------------------------------------------------------------------
SL_SYNC     .equ $53
CMD_PING    .equ $01
CMD_CHAT    .equ $02
CMD_WIKI    .equ $03
CMD_STORE   .equ $04
CMD_BOOK    .equ $05
CMD_WIFI_SCAN .equ $10
CMD_WIFI_SET  .equ $11
CMD_STATUS    .equ $12
CMD_TIME      .equ $13
CMD_OTA       .equ $20      ; start the ESP32 upload server window
CMD_CAS       .equ $30      ; Super-CAS text command -> text result
CMD_GAME      .equ $32      ; streamed games: [op][...] -> raw frame data (see docs/STATUS.md)
CMD_TURBO     .equ $33      ; [1] = switch both ends to the calculator-clocked turbo byte layer, [0] = back to safe
CMD_PLOT3D    .equ $31      ; plot3d(...) -> 768-byte bitmap (calculator frame buffer layout)
CMD_DIAG      .equ $15      ; link/ESP32 diagnostics report
CMD_BENCH     .equ $16      ; ESP32 returns N pseudo-random bytes (throughput test)
CMD_SLEEP     .equ $FF
RSP_MORE    .equ $80
RSP_LAST    .equ $81
RSP_ERR     .equ $82
RSP_READY   .equ $A5        ; ESP_READY frame: A5 5A
RSP_NOTIFY  .equ $90
SL_ACK      .equ $06
SL_NACK     .equ $15


; package directory entry copy (kernel/pkg.z80)
PK_PAGE     .equ 8
PK_OFF      .equ 9
PK_LEN      .equ 11
PK_TYPE     .equ 13
PK_FLAGS    .equ 14
PKGREC      .equ VARS+$B0       ; RAM copy of one directory entry (16 B)

; link diagnostics counters (kernel/superlink) and diag scratch
v_cnt_retry .equ VARS+$D0       ; 16-bit: frame retransmissions
v_cnt_crc   .equ VARS+$D2       ; 16-bit: received frames rejected (CRC / length)
v_cnt_tmo   .equ VARS+$D4       ; 16-bit: byte-level handshake timeouts
v_cnt_frames .equ VARS+$D6      ; 16-bit: frames exchanged ok
v_dgt0      .equ VARS+$D8       ; 16-bit tick at start of a measurement
v_dgok      .equ VARS+$DA
v_dgsum     .equ VARS+$DC       ; 16-bit accumulated ms
v_dgfont    .equ VARS+$DE
DGBUF       .equ PLOTSSCREEN+256   ; 16 B scratch for the diagnostics screens
WORKBUF     .equ PLOTSSCREEN+512   ; 64 B scratch (diagnostics)
v_turbo    .equ VARS+$E1        ; 1 = SuperLink turbo byte layer active
; crash trail: the ISR records where the CPU was on every tick; if the OS starts again while the marker says "running" (no deep sleep, no battery
; change in between) the last PC / SP are reported once on the home screen.  Lives in the unused tail of the SETTINGS block (never cleared at boot).
crash_mg   .equ SETTINGS+$38    ; $A5 $C3 while the OS runs
crash_pc   .equ SETTINGS+$3A    ; 16-bit: interrupted PC at the last tick
crash_sp   .equ SETTINGS+$3C    ; 16-bit: stack pointer at the last tick (before the ISR frame)
v_crash    .equ VARS+$E4        ; 1 = the previous run ended in an unexpected reset
v_cpc      .equ VARS+$E5        ; 16-bit
v_csp      .equ VARS+$E7        ; 16-bit
v_dgram    .equ VARS+$DF        ; bit n = RAM page n passed the diagnostics test
v_dgfl     .equ VARS+$E0        ; flash diagnostics: b0 guard, b1 erase, b2 program, b3 erase again
