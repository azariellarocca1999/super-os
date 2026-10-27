/* hz80_sim: headless TI-83 Plus Silver Edition runner on libtilemcore.
 *
 *   hz80_sim rom.bin out_prefix total_ms [events...]
 *
 * events:  T:down:ROW.BIT   T:up:ROW.BIT   (ROW -1 = ON key)
 *          T:snap:NAME      dump LCD as out_prefix_NAME.pbm and print a SNAP line
 *          T:bat:N          set battery level in 0.1 V (e.g. 60)
 *
 * environment:
 *   HZ_BRIDGE="cmd line"  co-simulate a bridge process on the link port. Two modes:
 *       HZ_LINKMODE=byte  (default) virtual GrayLink: whole bytes over the TI bit protocol
 *       HZ_LINKMODE=line  lockstep line-level co-simulation: used by the SuperLink turbo
 *                         protocol. The bridge receives "T <us> <calc_pulls>" messages
 *                         and answers "P <peer_pulls>".
 *   HZ_TRACE=n HZ_SKIP=ms   instruction trace
 *   HZ_DUMP=hexaddr HZ_DUMPLEN=n   dump CPU-visible memory at the end
 *   HZ_ROM=page:offset      peek at a flash byte (physical)
 *   HZ_LINKLOG=1            log link traffic on stderr
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#ifdef _WIN32
#include <windows.h>
#endif
#include <tilem.h>

/* libtilemcore expects the frontend to provide these. */
void *tilem_malloc(size_t n) { return malloc(n); }
void *tilem_malloc0(size_t n) { return calloc(1, n); }
void *tilem_malloc_atomic(size_t n) { return malloc(n); }
void *tilem_try_malloc(size_t n) { return malloc(n); }
void *tilem_try_malloc0(size_t n) { return calloc(1, n); }
void *tilem_try_malloc_atomic(size_t n) { return malloc(n); }
void *tilem_realloc(void *p, size_t n) { return realloc(p, n); }
void tilem_free(void *p) { free(p); }
const char *tilem_gettext(const char *m) { return m; }
void tilem_message(TilemCalc *c, const char *m, ...) {}
void tilem_warning(TilemCalc *c, const char *m, ...) {}
void tilem_internal(TilemCalc *c, const char *m, ...) {}

/* ---- statistics gathered through the I/O hooks -------------------------------- */
static unsigned wr3[256], nwr3 = 0, lcd_off_cmds = 0, lcd_on_cmds = 0;
static unsigned last_p4 = 0, last_contrast = 0, lowpower_p3 = 0, port20_writes = 0, last_p20 = 0;
static unsigned lcd_data_writes = 0;
static void (*real_out)(TilemCalc *, dword, byte);

static void out_hook(TilemCalc *c, dword port, byte v)
{
	port &= 0xff;
	if (port == 3) {
		if (nwr3 < 256) wr3[nwr3++] = v;
		if (!(v & 8)) lowpower_p3++;
	} else if (port == 4) last_p4 = v;
	else if (port == 0x20) { port20_writes++; last_p20 = v; }
	else if (port == 0x10) {
		if (v == 2) lcd_off_cmds++;
		if (v == 3) lcd_on_cmds++;
		if (v >= 0xC0) last_contrast = v & 0x3f;
	} else if (port == 0x11) lcd_data_writes++;
	real_out(c, port, v);
}

/* ---- LCD dump ------------------------------------------------------------------- */
static unsigned dump_lcd(TilemCalc *c, const char *prefix, const char *tag)
{
	byte lcd[12 * 64];
	char path[512];
	unsigned lit = 0;
	c->hw.get_lcd(c, lcd);
	snprintf(path, sizeof path, "%s%s%s.pbm", prefix, tag[0] ? "_" : "", tag);
	FILE *pf = fopen(path, "w");
	fprintf(pf, "P1\n96 64\n");
	for (int y = 0; y < 64; y++) {
		for (int x = 0; x < 96; x++) {
			int p = (lcd[y * 12 + x / 8] >> (7 - x % 8)) & 1;
			lit += p;
			fprintf(pf, "%d ", p);
		}
		fputc('\n', pf);
	}
	fclose(pf);
	return lit;
}

/* ---- bridge co-simulation --------------------------------------------------------- */
static HANDLE br_in = NULL, br_out = NULL;
static int linkmode_line = 0;

static int bridge_start(const char *cmdline)
{
	SECURITY_ATTRIBUTES sa = { sizeof sa, NULL, TRUE };
	HANDLE cin_r, cin_w, cout_r, cout_w;
	CreatePipe(&cin_r, &cin_w, &sa, 0);
	CreatePipe(&cout_r, &cout_w, &sa, 0);
	SetHandleInformation(cin_w, HANDLE_FLAG_INHERIT, 0);
	SetHandleInformation(cout_r, HANDLE_FLAG_INHERIT, 0);
	STARTUPINFOA si; PROCESS_INFORMATION pi;
	ZeroMemory(&si, sizeof si); si.cb = sizeof si;
	si.dwFlags = STARTF_USESTDHANDLES;
	si.hStdInput = cin_r; si.hStdOutput = cout_w; si.hStdError = GetStdHandle(STD_ERROR_HANDLE);
	char buf[1024]; snprintf(buf, sizeof buf, "%s", cmdline);
	if (!CreateProcessA(NULL, buf, NULL, NULL, TRUE, 0, NULL, NULL, &si, &pi)) return 0;
	CloseHandle(cin_r); CloseHandle(cout_w);
	br_in = cin_w; br_out = cout_r;
	return 1;
}

static void bridge_service_byte(TilemCalc *c)
{
	int r;
	DWORD n, got;
	while ((r = tilem_linkport_graylink_get_byte(c)) >= 0) {
		unsigned char b = (unsigned char) r;
		if (getenv("HZ_LINKLOG")) fprintf(stderr, "[link] calc->bridge %02X\n", b);
		WriteFile(br_in, &b, 1, &n, NULL);
	}
	if (tilem_linkport_graylink_ready(c) && PeekNamedPipe(br_out, NULL, 0, NULL, &got, NULL) && got > 0) {
		unsigned char b;
		if (ReadFile(br_out, &b, 1, &n, NULL) && n == 1) {
			if (getenv("HZ_LINKLOG")) fprintf(stderr, "[link] bridge->calc %02X\n", b);
			tilem_linkport_graylink_send_byte(c, b);
		}
	}
}

/* Line-level lockstep: after every slice, report the calc's pulled lines and the time
 * to the bridge; the bridge replies with the lines it pulls. Deterministic: the emulator
 * waits for the answer. */
static unsigned long long sim_us = 0;
static int last_calc_lines = -1;
static void bridge_service_line(TilemCalc *c)
{
	char line[128];
	DWORD n, got;
	int calc = c->linkport.lines & 3;
	static unsigned long long last_active_us = 0;
	static int peer_now = 0;
	if (calc != last_calc_lines || peer_now) last_active_us = sim_us;
	/* every slice while the link is busy (and for 3 ms after), otherwise once per millisecond */
	static unsigned long long last_sent_us = 0;
	if (calc == last_calc_lines && sim_us - last_active_us > 3000 && sim_us - last_sent_us < 1000) return;
	last_sent_us = sim_us;
	last_calc_lines = calc;
	int len = snprintf(line, sizeof line, "T %llu %d\n", sim_us, calc);
	WriteFile(br_in, line, len, &n, NULL);
	/* read one answer line */
	int i = 0; char ch;
	for (;;) {
		if (!ReadFile(br_out, &ch, 1, &got, NULL) || got == 0) return;
		if (ch == '\n') break;
		if (i < 100) line[i++] = ch;
	}
	line[i] = 0;
	int peer = 0;
	if (line[0] == 'P') peer = atoi(line + 2);
	peer_now = peer & 3;
	tilem_linkport_blacklink_set_lines(c, (byte)(peer & 3));
}



/* Advance exactly `us` microseconds of emulated time.  run_time() returns early on every link-line
 * change (TILEM_STOP_LINK_STATE), so keep going until the wanted amount has really elapsed, giving the
 * bridge a chance to answer after each early return. */
static void run_line_us(TilemCalc *c, int us)
{
	int khz = c->z80.clockspeed ? c->z80.clockspeed : 6000;
	dword target = c->z80.clock + (dword)((unsigned long long)us * khz / 1000);
	while ((int)(target - c->z80.clock) > 0) {
		dword before = c->z80.clock;
		int rem = (int)((unsigned long long)(target - before) * 1000 / khz);
		tilem_z80_run_time(c, rem > 0 ? rem : 1, NULL);
		sim_us += (unsigned long long)(c->z80.clock - before) * 1000 / khz;
		bridge_service_line(c);
	}
}

/* ---- live mode: interactive session for pc-simulator/simulator.py ---------------------------------
 *   hz80_sim --live rom.bin
 * stdin  : "D row.bit" / "U row.bit" (row -1 = ON), "Q" quits
 * stdout : "F <1536 hex chars>" LCD frames (when changed, at most every 40 ms), "S <ms> <halted%%>" stats
 * The calculator runs in real time; the optional bridge (HZ_BRIDGE, HZ_LINKMODE=line) is wired as usual.
 */
static int live_main(const char *romfile)
{
	FILE *rf = fopen(romfile, "rb");
	if (!rf) { perror("rom"); return 2; }
	TilemCalc *c = tilem_calc_new(TILEM_CALC_TI83P_SE);
	if (tilem_calc_load_state(c, rf, NULL)) { fprintf(stderr, "rom load failed\n"); return 2; }
	fclose(rf);
	int use_bridge = 0;
	if (getenv("HZ_BRIDGE")) {
		use_bridge = bridge_start(getenv("HZ_BRIDGE"));
		linkmode_line = getenv("HZ_LINKMODE") && !strcmp(getenv("HZ_LINKMODE"), "line");
		if (use_bridge && linkmode_line) c->linkport.linkemu = TILEM_LINK_EMULATOR_BLACK;
		else if (use_bridge) { c->linkport.linkemu = TILEM_LINK_EMULATOR_GRAY; tilem_linkport_graylink_reset(c); }
	}
	HANDLE hin = GetStdHandle(STD_INPUT_HANDLE);
	LARGE_INTEGER qf, q0; QueryPerformanceFrequency(&qf); QueryPerformanceCounter(&q0);
	byte last[12 * 64], cur[12 * 64];
	memset(last, 0xAA, sizeof last);
	unsigned long long ms = 0, halted = 0, lastframe = 0;
	setvbuf(stdout, NULL, _IOFBF, 1 << 16);
	for (;;) {
		DWORD avail = 0;
		char buf[256];
		if (PeekNamedPipe(hin, NULL, 0, NULL, &avail, NULL) && avail > 0) {
			DWORD n; ReadFile(hin, buf, avail < 255 ? avail : 255, &n, NULL); buf[n] = 0;
			char *p = buf;
			while (*p) {
				int g, b;
				if (*p == 'Q') return 0;
				if ((*p == 'D' || *p == 'U') && sscanf(p + 1, " %d.%d", &g, &b) == 2) {
					int sc = (g < 0) ? 0x29 : g * 8 + b + 1;
					if (*p == 'D') tilem_keypad_press_key(c, sc); else tilem_keypad_release_key(c, sc);
				}
				while (*p && *p != '\n') p++;
				if (*p) p++;
			}
		}
		if (use_bridge && linkmode_line) {
			for (int k = 0; k < 10; k++) run_line_us(c, 100);
		} else if (use_bridge) {
			for (int k = 0; k < 10; k++) { tilem_z80_run_time(c, 100, NULL); bridge_service_byte(c); }
		} else tilem_z80_run_time(c, 1000, NULL);
		ms++;
		if (c->z80.halted) halted++;
		c->hw.get_lcd(c, cur);
		if ((memcmp(cur, last, sizeof cur) || ms - lastframe > 500) && ms - lastframe >= 40) {
			memcpy(last, cur, sizeof cur);
			lastframe = ms;
			printf("F ");
			for (int i = 0; i < 768; i++) printf("%02x", cur[i]);
			printf("\nS %llu %.1f %d %d\n", ms, 100.0 * halted / ms, c->z80.clockspeed, c->lcd.active);
			fflush(stdout);
		}
		LARGE_INTEGER q; QueryPerformanceCounter(&q);
		while ((q.QuadPart - q0.QuadPart) * 1000 / qf.QuadPart < (long long)ms) { Sleep(1); QueryPerformanceCounter(&q); }
	}
}

typedef struct { int t; int kind; int scan; char name[32]; } Ev; /* kind: 0 up 1 down 2 snap 3 battery */

int main(int argc, char **argv)
{
	if (argc >= 3 && !strcmp(argv[1], "--live")) return live_main(argv[2]);
	if (argc < 4) { fprintf(stderr, "usage: hz80_sim rom out total_ms [events]\n"); return 2; }
	FILE *rf = fopen(argv[1], "rb");
	if (!rf) { perror("rom"); return 2; }
	TilemCalc *c = tilem_calc_new(TILEM_CALC_TI83P_SE);
	if (tilem_calc_load_state(c, rf, NULL)) { fprintf(stderr, "rom load failed (need a 2 MB image)\n"); return 2; }
	fclose(rf);

	int use_bridge = 0;
	if (getenv("HZ_BRIDGE")) {
		use_bridge = bridge_start(getenv("HZ_BRIDGE"));
		if (!use_bridge) { fprintf(stderr, "bridge start failed\n"); return 2; }
		linkmode_line = getenv("HZ_LINKMODE") && !strcmp(getenv("HZ_LINKMODE"), "line");
		if (linkmode_line) c->linkport.linkemu = TILEM_LINK_EMULATOR_BLACK;
		else { c->linkport.linkemu = TILEM_LINK_EMULATOR_GRAY; tilem_linkport_graylink_reset(c); }
	}
	LARGE_INTEGER qf, q0; QueryPerformanceFrequency(&qf); QueryPerformanceCounter(&q0);
	real_out = c->hw.z80_out;
	c->hw.z80_out = out_hook;

	if (getenv("HZ_SKIP")) tilem_z80_run_time(c, atoi(getenv("HZ_SKIP")) * 1000, NULL);
	if (getenv("HZ_TRACE")) {
		int n = atoi(getenv("HZ_TRACE"));
		for (int i = 0; i < n; i++) {
			TilemZ80Regs *r = &c->z80.r;
			printf("%04X: AF=%04X BC=%04X DE=%04X HL=%04X SP=%04X op=%02X%s\n", r->pc.w.l, r->af.w.l, r->bc.w.l, r->de.w.l, r->hl.w.l, r->sp.w.l,
			       c->hw.z80_rdmem(c, r->pc.w.l), c->z80.halted ? " HALT" : "");
			tilem_z80_run(c, 1, NULL);
		}
		return 0;
	}

	int total = atoi(argv[3]);
	static Ev ev[1024]; int nev = 0;
	for (int i = 4; i < argc && nev < 1024; i++) {
		int t, g, b, v; char dir[8], nm[32];
		if (sscanf(argv[i], "%d:snap:%31s", &t, nm) == 2) {
			ev[nev].t = t; ev[nev].kind = 2; strcpy(ev[nev].name, nm); nev++;
		} else if (sscanf(argv[i], "%d:softreset", &t) == 1 && strstr(argv[i], ":softreset")) {   /* CPU reset, RAM kept (a crash / the reset pinhole) */
				ev[nev].t = t; ev[nev].kind = 5; nev++;
			} else if (sscanf(argv[i], "%d:reset", &t) == 1 && strstr(argv[i], ":reset")) {
			ev[nev].t = t; ev[nev].kind = 4; nev++;
		} else if (sscanf(argv[i], "%d:bat:%d", &t, &v) == 2) {
			ev[nev].t = t; ev[nev].kind = 3; ev[nev].scan = v; nev++;
		} else if (sscanf(argv[i], "%d:%7[a-z]:%d.%d", &t, dir, &g, &b) == 4) {
			ev[nev].t = t; ev[nev].kind = !strcmp(dir, "down");
			ev[nev].scan = (g < 0) ? 0x29 : g * 8 + b + 1; nev++;
		}
	}

	unsigned halted_ms = 0, hz0000 = 0, hz0038 = 0, samePC = 0, slices = 0, nstack_bad = 0;
	unsigned lastpc = 0xffffffff, minsp = 0xffff, maxsp = 0;
	int e = 0;
	for (int t = 0; t < total; t++) {
		while (e < nev && ev[e].t <= t) {
			if (ev[e].kind == 1) tilem_keypad_press_key(c, ev[e].scan);
			else if (ev[e].kind == 0) tilem_keypad_release_key(c, ev[e].scan);
			else if (ev[e].kind == 3) c->battery = ev[e].scan;
			else if (ev[e].kind == 5) tilem_calc_reset(c);
				else if (ev[e].kind == 4) {   /* power cycle: RAM lost, flash kept */
				memset(c->mem + 0x200000, 0, 0x20000);
				tilem_calc_reset(c);
			}
			else {
				unsigned lit = dump_lcd(c, argv[2], ev[e].name);
				printf("SNAP %-10s t=%dms lit=%u lcd_active=%d halted_pct=%.1f pc=%04X contrast_cmd=%u speed_khz=%d\n", ev[e].name, t, lit, c->lcd.active,
				       slices ? 100.0 * halted_ms / slices : 0.0, c->z80.r.pc.w.l, last_contrast, c->z80.clockspeed);
			}
			e++;
		}
		if (use_bridge && linkmode_line) {
			for (int k = 0; k < 10; k++) run_line_us(c, 100);
		} else if (use_bridge) {
			for (int k = 0; k < 10; k++) { tilem_z80_run_time(c, 100, NULL); bridge_service_byte(c); }
			LARGE_INTEGER q; QueryPerformanceCounter(&q);
			while ((q.QuadPart - q0.QuadPart) * 1000 / qf.QuadPart < t) { Sleep(1); QueryPerformanceCounter(&q); bridge_service_byte(c); }
		} else {
			tilem_z80_run_time(c, 1000, NULL);
		}
		unsigned pc = c->z80.r.pc.w.l, sp = c->z80.r.sp.w.l;
		slices++;
		if (c->z80.halted) halted_ms++;
		else {
			if (pc < 0x0008 && t > 3) hz0000++;
			if (pc >= 0x0038 && pc < 0x0040) hz0038++;
			if (pc == lastpc) samePC++;
		}
		lastpc = pc;
		if (sp < minsp) minsp = sp;
		if (sp > maxsp) maxsp = sp;
		if (sp != 0 && sp < 0x8000) nstack_bad++;
	}

	if (getenv("HZ_ROM")) {
		unsigned pg, off; sscanf(getenv("HZ_ROM"), "%x:%x", &pg, &off);
		int rl = getenv("HZ_ROMLEN") ? atoi(getenv("HZ_ROMLEN")) : 1;
		if (rl > 1) { printf("ROMDUMP %02X:%04X:", pg, off); for (int i = 0; i < rl; i++) printf(" %02X", c->mem[pg * 0x4000 + off + i]); printf("\n"); }
		printf("ROM %02X:%04X = %02X (flash.unlock=%d)\n", pg, off, c->mem[pg * 0x4000 + off], c->flash.unlock);
	}
	if (getenv("HZ_DUMP")) {
		unsigned a = strtoul(getenv("HZ_DUMP"), NULL, 16), n = getenv("HZ_DUMPLEN") ? atoi(getenv("HZ_DUMPLEN")) : 32;
		printf("MEM %04X:", a);
		for (unsigned i = 0; i < n; i++) printf(" %02X", c->hw.z80_rdmem(c, (a + i) & 0xffff));
		printf("\n");
	}
	unsigned lit = dump_lcd(c, argv[2], "");
	printf("PC=%04X SP=%04X halted=%d lcd_active=%d contrast=%u speed_khz=%d\n", c->z80.r.pc.w.l, c->z80.r.sp.w.l, c->z80.halted, c->lcd.active, last_contrast, c->z80.clockspeed);
	printf("slices=%u halted_pct=%.1f stuck_at_reset_vec=%u stuck_at_0038=%u same_pc=%u bad_sp=%u\n", slices, 100.0 * halted_ms / slices, hz0000, hz0038, samePC, nstack_bad);
	printf("sp_range=%04X..%04X lit_pixels=%u lcd_off_cmds=%u lcd_on_cmds=%u lowpower_p3_writes=%u last_p4=%02X port20_writes=%u last_p20=%02X lcd_data_writes=%u\n",
	       minsp, maxsp, lit, lcd_off_cmds, lcd_on_cmds, lowpower_p3, last_p4, port20_writes, last_p20, lcd_data_writes);
	printf("port3_writes:"); for (unsigned i = 0; i < nwr3 && i < 16; i++) printf(" %02X", wr3[i]); printf(" (n=%u)\n", nwr3);
	return 0;
}
