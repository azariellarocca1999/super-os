# Games

All games run on the calculator alone (the ESP32 is only needed for the streamed ones). They share one small library (`z80-os/games/glib.z80`): 27 frames per second, the matrix keyboard scanned directly, MODE or CLEAR pauses, a long idle puts the calculator to sleep, and every game keeps its **best score** while the calculator has power (it survives sleep, not a battery change).

**Keys in every game:** arrows move · `2ND` or `ENTER` = main action · `ALPHA` or `DEL` = second action · `MODE` or `CLEAR` = pause (then `ENTER` resumes, `CLEAR` leaves).

| # (F4 tab) | Game | Controls | Notes |
|---|---|---|---|
| 1 | **Tetris** | ◄ ► move (auto-repeat) · `▲` or `2ND` rotate · ▼ soft drop · `ALPHA` hard drop | 10x16 board, 7-bag randomizer, wall kicks, ghost piece, next piece, line-clear flash, levels every 10 lines |
| 2 | **Snake** | arrows steer | 22x13 field, speeds up every 4 apples, walls and tail are deadly |
| 3 | **Breakout** | ◄ ► move (hold = faster) · `2ND` / `ENTER` / `ALPHA` launch | 8x5 bricks, bounce angle depends on where the paddle is hit, 3 lives, narrower paddle from level 4 |
| 4 | **Pong** | ▲ ▼ move | first to 7; the CPU follows the ball with a random aiming error and gets sharper if you lead |
| 5 | **2048** | arrows slide · `ALPHA` undo (once) | tiles from 64 up are inverted; the 2048 tile shows a message and the game goes on |
| 6 | **Invaders** | ◄ ► move · `2ND` / `ENTER` / `ALPHA` / `▲` fire | 4x8 aliens that speed up as they die, three destructible bunkers, a bonus ship, endless waves |
| 7 | **Minesweeper** | arrows move · `2ND` / `ENTER` reveal · `ALPHA` flag | 16x9 field, 18 mines, first reveal is safe and opens a region; best = fastest win |
| 8 | **Classics (CHIP-8)** | number pad = CHIP-8 keypad, arrows = 2 4 6 8, `ENTER` = 5, `CLEAR` quits | PONG, BREAKOUT, SNAKE, INVADERS, DODGE, SIMON, running in a CHIP-8 interpreter |
| 9 | **Stream 3D** | see in-game | needs the ESP32: a ray-cast maze and the Game Boy test ROM dmg-acid2, plus any ROM you upload |

Adding your own CHIP-8 games: assemble with `tools/chip8.py` (sources in `games/chip8`), or `python tools/ota_push.py game.c8 --kind game` once the ESP32 is connected. Only use ROMs you have the right to use.

Writing a new native game: copy a small one (`snake.z80`), use `gl_init` / `gl_tick` / `gl_rect` / `gl_spr` / `gl_text` / `gl_gameover` from `glib.z80`, add an entry to the jump table in `page5.z80`, a string in `tools/gen_strings.py`, a launcher in `ui/mathapps.z80` and a line in the GAMES tab of `ui/home.z80`; add a bot to `tools/selftest_games.py`.
