#!/usr/bin/env python3
"""Generate the bilingual (ES/EN) string tables for the UI.

Writes build/strings.inc (STR_xxx equates = byte offset into the table) and
build/strings.z80 (two pointer tables + data).  The font is upper-case ASCII only, so
text is upper-cased and accents folded here.
"""
import os
import unicodedata

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (id, ES, EN)
S = [
    ("TAB_HOME", "INIC", "HOME"), ("TAB_MATH", "MATE", "MATH"), ("TAB_AI", "IA", "AI"),
    ("TAB_GAMES", "JUEG", "GAME"), ("TAB_SYS", "SIST", "SYS"),
    ("APP_CHAT", "CHAT IA", "AI CHAT"), ("APP_STEP", "PASO/PASO", "STEPS"),
    ("APP_WIKI", "INTERNET", "INTERNET"), ("APP_CLOCK", "RELOJ", "CLOCK"),
    ("APP_DASH", "PANEL", "DASHBOARD"), ("APP_WIFI", "WIFI+API", "WIFI+API"),
    ("APP_SET", "AJUSTES", "SETTINGS"), ("APP_SLEEP", "DORMIR", "SLEEP"), ("APP_INFO", "INFO", "INFO"),
    ("APP_BOOKS", "LIBROS", "BOOKS"), ("APP_WEATHER", "CLIMA", "WEATHER"), ("APP_CALC", "CALCULAD.", "CALCULATOR"),
    ("APP_GRAPH", "GRAFICAR", "GRAPH"), ("APP_CAS", "SUPER-CAS", "SUPER-CAS"),
    ("APP_PTABLE", "PERIODICA", "PERIODIC"), ("APP_CONV", "CONVERSOR", "CONVERTER"),
    ("APP_CONST", "CONSTANTES", "CONSTANTS"), ("APP_OTA", "OTA WIFI", "OTA WIFI"),
    ("APP_PACKA", "ARCADE", "ARCADE"), ("APP_PACKB", "ACCION", "ACTION"), ("APP_PACKC", "STREAM 3D", "STREAM 3D"),
    ("APP_EMU", "EMULAD.", "EMULATORS"), ("APP_TETRIS", "TETRIS", "TETRIS"), ("APP_SNAKE", "SERPIENTE", "SNAKE"), ("APP_BREAK", "LADRILLOS", "BREAKOUT"), ("APP_PONG", "PONG", "PONG"), ("APP_2048", "2048", "2048"), ("APP_INVAD", "INVASORES", "INVADERS"), ("APP_MINES", "MINAS", "MINES"), ("APP_CLASSIC", "CLASICOS", "CLASSIC"),
    ("APP_SOKOBAN", "SOKOBAN", "SOKOBAN"), ("APP_REVERSI", "REVERSI", "REVERSI"), ("APP_MORE", "MAS...", "MORE..."), ("APP_BACK", "VOLVER", "BACK"),
    ("DG_7", "7 TIEMPOS", "7 TIMING"), ("DG_T7", "TIEMPOS", "TIMING"), ("DG_WAIT", "MIDIENDO...", "MEASURING..."),
    ("DG_T7H", "ENTER=OTRA CLEAR=SALIR", "ENTER=AGAIN CLEAR=EXIT"),
    ("CRASH_T", "REINICIO", "RESET"), ("CRASH_1", "SE REINICIO SOLA", "UNEXPECTED RESTART"), ("CRASH_2", "ANOTA PC Y SP:", "NOTE PC AND SP:"),
    ("HINT_HOME", "F1-F5 TABS 1-9 +/- LCD", "F1-F5 TABS 1-9 +/- LCD"),

    ("NOLINK", "SIN RESPUESTA ESP32", "NO ANSWER FROM ESP32"),
    ("WAITING", "ESPERANDO...", "WAITING..."),
    ("PRESSKEY", "PULSA UNA TECLA", "PRESS ANY KEY"),
    ("L_LANG", "IDIOMA", "LANGUAGE"), ("L_BAT", "PILAS", "BATTERY"), ("L_CONTRAST", "CONTRASTE", "CONTRAST"),
    ("L_SLEEP", "SUENO CALC S", "CALC SLEEP S"), ("L_ESPSLEEP", "SUENO ESP S", "ESP SLEEP S"),
    ("L_FONT", "FUENTE", "FONT"), ("L_CLOCKSET", "PONER HORA", "SET TIME"),
    ("V_ES", "ESPANOL", "ESPANOL"), ("V_EN", "ENGLISH", "ENGLISH"),
    ("V_PROF0", "ALCALINA AAA", "ALKALINE AAA"), ("V_PROF1", "NIMH AAA 4.8V", "NIMH AAA 4.8V"),
    ("V_PROF2", "LI-ION/LIPO", "LI-ION/LIPO"),
    ("V_FONTS", "4X6 24X10", "4X6 24X10"), ("V_FONTB", "6X8 16X8", "6X8 16X8"),
    ("SET_HELP", "ARRIBA/ABAJO  IZQ/DER", "UP/DOWN  LEFT/RIGHT"),
    ("D_BAT", "PILAS", "BATTERY"), ("D_CPU", "CPU", "CPU"), ("D_RAM", "BANCOS RAM", "RAM BANKS"),
    ("D_FLASH", "FLASH LIBRE", "FLASH FREE"), ("D_ESP", "ESP32", "ESP32"), ("D_UP", "ENCENDIDO S", "UPTIME S"),
    ("D_HALT", "HALTS", "HALTS"), ("D_SLEEPS", "DORMIDAS", "SLEEPS"), ("D_TASKS", "TAREAS", "TASKS"),
    ("D_KEYS", "ENTER=ESP SUENO", "ENTER=ESP SLEEP"),
    ("C_TITLE", "RELOJ", "CLOCK"), ("C_SYNC", "ENTER = SINCRONIZAR NTP", "ENTER = SYNC NTP"),
    ("C_SET", "+/- AJUSTAR HORA", "+/- ADJUST TIME"),
    ("W_SCAN", "BUSCANDO REDES...", "SCANNING..."), ("W_PICK", "ELEGI CON 1-9", "PICK WITH 1-9"),
    ("W_PASS", "CLAVE WIFI", "WIFI PASSWORD"), ("W_OK", "ENVIADO AL ESP32", "SENT TO ESP32"),
    ("W_API", "API KEY DEEPSEEK", "DEEPSEEK API KEY"), ("W_MENU1", "1 REDES WIFI", "1 WIFI NETWORKS"),
    ("W_MENU2", "2 API KEY", "2 API KEY"),
    ("Q_CHAT", "PREGUNTA", "QUESTION"), ("Q_MODEL", "ALPHA=MODO  ENTER=ENVIAR", "ALPHA=MODE  ENTER=SEND"),
    ("M_V3", "DEEPSEEK-CHAT V3", "DEEPSEEK-CHAT V3"), ("M_R1", "DEEPSEEK-REASONER R1", "DEEPSEEK-REASONER R1"),
    ("O_REMOTE", "1 PAQUETES EN LA PC", "1 PC PACKAGES"), ("O_INST", "2 INSTALADOS", "2 INSTALLED"),
    ("O_FORMAT", "3 BORRAR TODO", "3 ERASE ALL"), ("O_RECV", "4 RECIBIR DE LA PC", "4 RECEIVE FROM PC"),
    ("O_OK", "INSTALADO", "INSTALLED"), ("O_FAIL", "NO SE PUDO INSTALAR", "INSTALL FAILED"),
    ("O_RUNDEL", "ENTER=CORRER DEL=BORRAR", "ENTER=RUN DEL=DELETE"), ("O_NONE", "(SIN PAQUETES)", "(NO PACKAGES)"),
    ("O_CONFIRM", "ENTER = BORRAR TODO", "ENTER = ERASE ALL"), ("O_DONE", "LISTO", "DONE"),
    ("O_BIG", "PAQUETE MUY GRANDE", "PACKAGE TOO BIG"), ("O_PICK", "ELEGI CON 1-9", "PICK WITH 1-9"),
    ("APP_DIAG", "DIAGNOST.", "DIAGNOST."), ("DG_TITLE", "DIAGNOSTICO", "DIAGNOSTICS"),
    ("DG_1", "1 ENLACE ESP32", "1 ESP32 LINK"), ("DG_2", "2 PANTALLA LCD", "2 LCD"), ("DG_3", "3 TECLADO", "3 KEYBOARD"),
    ("DG_4", "4 RAM 128K", "4 RAM 128K"), ("DG_5", "5 FLASH", "5 FLASH"), ("DG_6", "6 INFORME ESP32", "6 ESP32 REPORT"),
    ("APP_NOTES", "NOTAS", "NOTES"), ("NT_EDIT", "NOTA", "NOTE"), ("NT_HINT", "1-4 ABRIR DEL+N BORRAR", "1-4 OPEN DEL+N ERASE"),
    ("APP_LOCK", "BLOQUEO", "LOCK"), ("LK_1", "1 PIN", "1 PIN"), ("LK_2", "2 MODO EXAMEN", "2 EXAM MODE"),
    ("LK_3", "3 DESACTIVAR", "3 TURN OFF"), ("LK_4", "4 BLOQUEAR YA", "4 LOCK NOW"),
    ("LK_S0", "ESTADO: LIBRE", "STATE: OFF"), ("LK_S1", "ESTADO: PIN", "STATE: PIN"), ("LK_S2", "ESTADO: EXAMEN", "STATE: EXAM"),
    ("PIN_NEW", "PIN NUEVO", "NEW PIN"),
    ("PIN_AGAIN", "REPETI EL PIN", "REPEAT THE PIN"),
    ("PIN_DIFF", "NO COINCIDEN", "NO MATCH"), ("EXAM_BLK", "EXAMEN: CERRADO", "EXAM: CLOSED"),
    ("B_1", "1 MUESTRA (ROM ZX0)", "1 SAMPLE (ROM ZX0)"), ("B_3", "3 DEMO TI-OS", "3 TI-OS DEMO"),
]


def clean(t):
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.upper().encode("ascii", "replace").decode("ascii")


def main():
    build = os.path.join(root, "build")
    os.makedirs(build, exist_ok=True)
    inc = ["; GENERATED by tools/gen_strings.py\n"]
    z = ["; GENERATED by tools/gen_strings.py\nstr_table_es:\n"]
    for i, (n, es, en) in enumerate(S):
        inc.append("STR_%-10s .equ %d\n" % (n, i * 2))
        z.append("    .dw s_es_%d\n" % i)
    z.append("str_table_en:\n")
    for i, _ in enumerate(S):
        z.append("    .dw s_en_%d\n" % i)
    for i, (n, es, en) in enumerate(S):
        z.append('s_es_%d: .db "%s",0\n' % (i, clean(es).replace('"', "'")))
        z.append('s_en_%d: .db "%s",0\n' % (i, clean(en).replace('"', "'")))
    open(os.path.join(build, "strings.inc"), "w").write("".join(inc))
    open(os.path.join(build, "strings.z80"), "w").write("".join(z))
    print(len(S), "strings")


if __name__ == "__main__":
    main()
