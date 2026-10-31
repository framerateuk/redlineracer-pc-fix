# Redline Racer (PC, 1998) on modern PCs and the Steam Deck

## Why this exists

Redline Racer looked amazing when it was released. I remember having a demo on a PC Format cover
disc, but it wouldn't run because my system didn't have the 32 MB of RAM it needed, and it took a
long time to track the game down. It's not as good as Moto Racer, but it's a good-looking racer.
On modern systems it stops at a CD check that can't be passed, and a modern pad's triggers don't
work as throttle and brake. This kit sorts that out, so it can be played again.

Its follow-up on the same engine, Suzuki Alstare Extreme Racing, has its own kit:
[suzukialstare-pc-fix](https://github.com/framerateuk/suzukialstare-pc-fix).

## What this does

Turns **your own** Redline Racer CD into a folder that runs on the Steam Deck (Proton) or on
Windows 10/11, with no installer and no registry entries:

- **Copied straight from the CD**: what the installer copies for a full English Direct3D install.
- **Direct3D through dgVoodoo2**: the game's only mode, 640x480, rendered at your screen's height,
  4:3 with black bars, held at 60 frames a second (above 60 the bikes misbehave).
- **CD soundtrack** from OGG files ripped from your disc.
- **Gamepad**: an Xbox-style pad (the Steam Deck's included) is read directly, with analogue
  throttle and brake on the two triggers and analogue steering. The pad skips the start-up logos.
- **The CD check**: it wants a full, read-only drive holding the game, which a disc image or a
  Proton folder can't be, so it's patched out.
- No mouse pointer, and the menus' web-site button and F1 help no longer open a web browser.

**No game files are in this repository.** Everything from the game comes from your disc when you
run `build.py`.

## What you need

| | |
|---|---|
| The game | The **Redline Racer CD** (Criterion / Ubi Soft, 1998, the English / French / German / Italian / Spanish release, `rlr_D3d.exe` of 9 July 1998) as `.cue` + `.bin` or CloneCD `.ccd` + `.img`, with its audio tracks. `build.py` checks the exe and stops on another version. |
| Python | 3.8 or newer (python.org on Windows; already on macOS/Linux). |
| An OGG encoder | `oggenc` (vorbis-tools; Windows builds at rarewares.org) or `ffmpeg`, on the PATH. |
| dgVoodoo2 **2.79.3** | by Dege: [GitHub release v2.79.3](https://github.com/dege-diosg/dgVoodoo2/releases/tag/v2.79.3). Use 2.79.3: newer versions don't start under Wine/Proton. Keep the zip as downloaded. |
| ogg-winmm **v2025.01.16** | by AyuanX: [GitHub releases](https://github.com/ayuanx/ogg-winmm/releases). This exact release: `build.py` patches one call in its `winmm.dll` and checks the file first. Keep the zip as downloaded. |

## Build

```
python3 build.py rlr.ccd --dgvoodoo dgVoodoo2_79_3.zip --ogg-winmm ogg-winmm_binary.zip
```

creates `RedlineRacer/` with `game/` and `redline_launch.sh` (for the Steam Deck), in about a
minute. The same `game/` folder runs on Windows; `--windows` leaves out the launch script.
`--out DIR` puts the result somewhere else. The disc's original exes (the Direct3D and 3dfx ones),
settings file and readme are kept in `game/_spare/`.

## Play on the Steam Deck

1. Copy `RedlineRacer/` to the Deck, for example to `/home/deck/Games/RedlineRacer/`.
2. Desktop Mode: Steam > Add a Non-Steam Game > Browse > `.../RedlineRacer/game/rlr_D3d.exe`.
   Rename the shortcut "Redline Racer".
3. Properties > Compatibility: force **Proton 9.0**. Pin it rather than floating on Experimental.
4. Properties > Launch Options:
   ```
   /home/deck/Games/RedlineRacer/redline_launch.sh %command%
   ```
5. Controller layout: start from the standard **Gamepad** layout and set these to keyboard keys:
   **Start = Enter**, **View = Esc**, **D-pad = arrow keys**, **Y = F3** (next camera). The
   menus take the pad only to move and choose; back, pause and the camera are keys.

## Play on Windows

Run `game/rlr_D3d.exe`. An Xbox pad works as on the Deck, except those four: use Enter, Esc, the
arrow keys and F3 on the keyboard, or map them in Steam or your pad software. The D-pad also moves
in the menus and steers.

## Controls

| Pad | In a race | In the menus |
|---|---|---|
| Left stick | steer (analogue) | move |
| RT / LT | throttle / brake (analogue; both at once work) | |
| X | turbo | |
| A | "signal" | choose |
| RB / LB | gear up / down (manual gearbox; the default is automatic) | |
| Y (F3) | next camera view | |
| D-pad (arrows) | | move |
| Start (Enter) | | choose |
| View (Esc) | pause menu | back |

Options > Controls rebinds them (one input per control, saved in `game/menudata.ini`). With the pad
bindings the keyboard doesn't drive; the disc's keyboard bindings are in
`_spare/menudata-1998.ini`. Other keys: F2 / F3 previous / next camera, F5-F8 a camera directly.

## Settings

Everything is in `game/menudata.ini`, written by the game. The kit's copy is the disc's with the pad
bindings and the highest geometry detail and view distance. Best times and ghosts go in
`game/tracks/*.loc`, progress in `game/misc/database.ddb`.

- Sharper or softer: `[DirectX] Resolution` in `game/dgVoodoo.conf`.
- Deck renderer: `RENDERER=wined3d` before the script path in the launch options uses Wine's own
  Direct3D instead of dgVoodoo (no frame cap).

**Widescreen**: not included. The only fix, AlphaYellow's FOV fix, widens the 3D but leaves every
menu and HUD element stretched, because the game draws them all in 640x480 pixels.

## Troubleshooting

- *"Please reinsert the Red Line Racer CD"*: you're running the unpatched exe from `_spare/`.
- *No music*: on the Deck `launch.log` must show `WINEDLLOVERRIDES=...;winmm=n,b` (no log: the
  launch option is missing `%command%`), and `game/Music/Track02.ogg` must exist.
- *Bikes won't move, or accelerate strangely*: the frame rate is over 60. Keep `FPSLimit = 60` in
  `game/dgVoodoo.conf`.
- *Low-detail textures*: dgVoodoo's video memory set to 2 GB or more reads as negative to the game;
  keep `VRAM = 256`.
- *Judder on a G-Sync / FreeSync monitor*: turn variable refresh off for this game.

## What's in this repository

| File | What |
|---|---|
| `build.py` | Builds the folder: copies the CD's game files, patches the exe, hides the menu pointer, rips the soundtrack, adds the wrappers and settings. Python standard library only. |
| `patch_exe.py` | The exe patches, each explained; adds a code section to the exe. Also runs on its own. |
| `caves.s` | The new code's source (x86 assembly). `python3 patch_exe.py --check-caves` re-assembles it with clang and checks it against the bytes in `patch_exe.py`. |
| `oggwinmm_fix.py` | A 5-byte fix to ogg-winmm v2025.01.16 (its "open cdaudio" string command crashes under Wine). |
| `disc.py` | Reads the CD image: `.cue`/`.bin` or `.ccd`/`.img`, ISO 9660 with Joliet names, and audio tracks. |
| `config/` | The game's settings with the pad set up, dgVoodoo2's and ogg-winmm's. |
| `steamdeck/redline_launch.sh` | Proton launch wrapper: DLL overrides. |
| `docs/TECHNICAL.md` | How the game works and what each patch does. |

## Credits

- **Imagism** and **Criterion Studios** made Redline Racer; **Ubi Soft** published it. Please own
  the game: this kit needs your disc.
- **Dege**: dgVoodoo2. **AyuanX**: ogg-winmm.

## License

The scripts and docs in this repository: MIT (see `LICENSE`). The license covers only this
repository's own files, not the game, dgVoodoo2 or ogg-winmm.

Not affiliated with or endorsed by the game's rights holders.
