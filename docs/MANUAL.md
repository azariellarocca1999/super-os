# Super-OS: short user manual / Manual corto

## English

**Keys.** `F1`-`F5` (Y= WINDOW ZOOM TRACE GRAPH) switch the tabs INIC / MATE / IA / JUEG / SIST; the number keys 1-9 open the listed entries; `CLEAR` goes back; `2ND`+`ON` sleeps at once; `2ND`+`MODE` leaves the calculator.
**Text entry.** `ALPHA` cycles T9 / ABC / 123, `2ND` = upper case, `DEL` erases, `CLEAR` clears or leaves.
**Calculator (F2, 1).** Type like on a TI: `2+3*4`, `sin(30)` (`MODE` = DEG/RAD), `5 STO A`, `ANS`, `2ND`+`ENTER` recalls the last entry, `MATH` opens the function menu.
**Grapher (F2, 2).** `Y=` edit functions, `WINDOW` ranges, `ZOOM` presets, `GRAPH` draws, `TRACE` reads values, `2ND`+`GRAPH` shows the table.
**Information apps (F2, 5-7).** Periodic table (arrows, `ENTER` = detail), converter (1/2 units, 3 value, 4 swap), constants (`ENTER` twice stores in ANS).
**Games (F4).** `1` Tetris, `2` Snake, `3` Breakout, `4` Pong, `5` 2048, `6` Invaders, `7` Minesweeper, `8` CHIP-8 classics, `9` streamed games (needs the ESP32). Arrows move, `2ND` / `ENTER` = main action, `ALPHA` / `DEL` = second action, `MODE` / `CLEAR` = pause (then `ENTER` resumes and `CLEAR` leaves). Details: `docs/GAMES.md`.
**Settings (F1, 6).** Language, battery profile (alkaline / NiMH / Li-ion: pick the one that matches your cells), contrast trim, sleep delay.
**With the ESP32 (not required for the above).** AI chat, Step by step, Super-CAS, Wikipedia, weather, Wi-Fi/API setup, OTA packages, streamed games. Without it these apps show `SIN RESPUESTA ESP32` after about 6 seconds; `CLEAR` cancels the wait.
**Diagnostics (F5, 7).** LCD, keys, RAM, flash, ESP32 link and report, and `7 TIMING` (real tick rate and CPU speed); use them first on a new unit. If the calculator restarted by itself the next boot shows `REINICIO` with `PC` and `SP`: please report them.

## Español

**Teclas.** `F1`-`F5` cambian de pestaña (INIC / MATE / IA / JUEG / SIST); las teclas 1-9 abren las entradas de la lista; `CLEAR` vuelve atrás; `2ND`+`ON` apaga al instante; `2ND`+`MODE` sale de la calculadora.
**Texto.** `ALPHA` alterna T9 / ABC / 123, `2ND` = mayúsculas, `DEL` borra, `CLEAR` limpia o sale.
**Calculadora (F2, 1).** Se escribe como en una TI: `2+3*4`, `sin(30)` (`MODE` = DEG/RAD), `5 STO A`, `ANS`, `2ND`+`ENTER` repite la última entrada, `MATH` abre el menú de funciones.
**Graficador (F2, 2).** `Y=` funciones, `WINDOW` rangos, `ZOOM` ajustes, `GRAPH` dibuja, `TRACE` lee valores, `2ND`+`GRAPH` tabla.
**Apps de información (F2, 5-7).** Tabla periódica, conversor y constantes.
**Juegos (F4).** `1` Tetris, `2` Serpiente, `3` Ladrillos, `4` Pong, `5` 2048, `6` Invasores, `7` Minas, `8` clásicos CHIP-8, `9` juegos en streaming (necesitan el ESP32). Flechas mueven, `2ND` / `ENTER` = acción principal, `ALPHA` / `DEL` = acción secundaria, `MODE` / `CLEAR` = pausa (`ENTER` sigue, `CLEAR` sale). Detalles en `docs/GAMES.md`.
**Ajustes (F1, 6).** Idioma, perfil de batería (alcalina / NiMH / Li-ion: elegí el que corresponda a tus pilas), contraste, tiempo de reposo.
**Con el ESP32 (no hace falta para lo anterior).** Chat IA, Paso a paso, Super-CAS, Wikipedia, clima, WiFi/API, paquetes OTA, juegos en streaming. Sin él muestran `SIN RESPUESTA ESP32` a los ~6 s; `CLEAR` cancela la espera.
**Diagnósticos (F5, 7).** LCD, teclado, RAM, flash, enlace e informe del ESP32 y `7 TIEMPOS` (ritmo real del reloj y velocidad de la CPU); usalos primero en una unidad nueva. Si la calculadora se reinició sola, el próximo arranque muestra `REINICIO` con `PC` y `SP`: por favor reportalos.
