# How it works

Notes on Redline Racer (Imagism / Criterion Studios / Ubi Soft, 1998), the five-language European CD
(volume `980710_1014`, 10 July 1998; `DATA.TAG` version 1.00.000), `rlr_D3d.exe` 875,008 bytes,
linked 9 July 1998, MD5 `423fdb4f70f1a95a3607c1b4006ad886`. Addresses are virtual addresses in that
exe.

## The disc and the installer

Track 1 is the data track; tracks 2-7 are the music (track 7 is 8 seconds of silence). The disc
holds three builds, each its own exe: `rlr_D3d.exe` (Direct3D), `rlr_3dfx.exe` (Glide 2) and
`rlr_i740.exe` (Intel i740), with `selector.exe` picking 3dfx when `glide2x.dll` answers. The engine
is Criterion's RenderWare. No movies: the start-up logos are bitmap animations with `.wav` sound.

The InstallShield 5 installer's `data1.cab` holds only the file list: every installed file is read
from the disc's own folders. `build.py` copies what a full English Direct3D install puts in the game
folder ("Basic Files", "Direct3D Files", "Language Independant Files", "Empty Directories",
"English Files"), using the disc's Joliet names (its plain ISO 9660 names are upper-case 8.3). It
writes `Gameinst.ini` as the installer does (`CD=.\`, `Language=english`, `CDInstall=FALSE`; the
disc's copy holds the developers' `c:\redline\redline\`). With `CDInstall=FALSE` the game reads
everything from its own folder. The exe imports no registry function at all.

## The patches

`patch_exe.py` adds a section `.rdeck` (VA 0x556000, 4 KB, at the end of the file) holding the new
code from `caves.s`. Its header lists each site's bytes and how it was found.

| Patch | Hooks | Was | Now |
|---|---|---|---|
| `nocd` | the CD check 0x41da30 ("Please reinsert the Red Line Racer CD"): a `GetDiskFreeSpaceA` loop over C: to Y: for a full drive holding `common\normal.dff` that won't open for writing | Under Wine no folder can pass (its free space is the host disk's); the "insert CD" screen, then quit | Returns "found" at once |
| `pad` | the joystick read 0x418b80, called by the input pump every frame (0x443ee8) and by the Controls screen (0x431179); the pump's "a joystick was found" test 0x443ed3 | DirectInput: under Proton an Xbox pad's triggers are one Z axis (both held = neither) | The game's joystick struct written from XInput: left stick = X / Y, RT / LT = the two "sliders" (0..1 each), A B X Y LB RB View Start L3 R3 = buttons 0-9, D-pad = full stick. In the menus only A, only when newly pressed (they take any button as "choose" and repeat it while held). No XInput pad: the game's own read |
| `logoskip` | the logo loops 0x4334d0: their "typed key?" calls 0x43358f / 0x4335f2 | Skipped only by a key | Also A, B, X, Y, View or Start |
| `nocursor` | `RegisterClassA` "RedLine" (0x416bb4): its `LoadCursorA(0, IDC_ARROW)` (0x416b8b) | The class had the arrow | No class cursor (the window already answers `WM_SETCURSOR` with `SetCursor(NULL)`) |
| `noweb` | the two `ShellExecuteA` calls: the main menu's web-site button (0x4247aa) and F1 help (0x42a82e) | Opened a web browser (over the game) | Do nothing, report success |

The menus also draw their own pointer, `UiData\Cursors\default.bmp`, wherever `default.msk` isn't 0;
`build.py` zeroes the mask (an 8-bit 10x20 bitmap), so it's drawn nowhere. The mouse still clicks.

## Picture

The game is Direct3D 5 (DrawPrimitive through `IDirect3DDevice2`) on DirectDraw, full screen
640x480 x 16, hard-wired (0x4169e0). dgVoodoo2 2.79.3: `Resolution = max` renders at the screen's
height while the game thinks 640x480, `ScalingMode = stretched_ar` keeps 4:3 with black bars, 32-bit
internal precision, vsync, `FPSLimit = 60`. The Glide exe would need its own patch set (other
addresses), so it's kept in `_spare/` only.

Widescreen: AlphaYellow's "Redline Racer FOV Fix" corrects only the 3D camera for a picture stretched
from 640x480 to the wide screen; the HUD, menus and overlays are drawn in 640x480 pixels and would
stay stretched. So it isn't used.

**Frame rate.** The physics take the frame time from `timeGetTime` (0x43e6c0) and run it in 10 ms
sub-steps (0x43e700), but above 60 frames a second acceleration, braking and turning go wrong, and
with no limit at all `timeGetTime`'s 1 ms steps give zero-length frames and bikes that can't move.
dgVoodoo's vsync and `FPSLimit = 60` hold 60.

**Detail.** The starting `menudata.ini` sets the highest geometry detail and view distance. The
highest texture detail depends on the video memory the game measures (0x4401f0), which it reads as
a *signed* number: dgVoodoo's VRAM at 2 GB or more would read as negative and give the lowest
textures. 256 MB is right.

## Music

The game opens the MCI `cdaudio` device by type (no drive letter), sets TMSF and plays track n
"from n to n+1" with no notify; it loops by polling the device every 10 s from a `timeSetEvent`
timer (0x451770). Nothing waits for a notification, so ogg-winmm's missing "aborted" notification
can't freeze it. The music volume goes through `auxSetVolume`, which ogg-winmm handles.

## Pad

The game binds each control to one input (Options > Controls; saved in `menudata.ini` as
`PlayerControl<name>Event / Param / Digital`). A joystick binding's parameter (0x452010): 0 / 1 =
stick left / right, 2 / 3 = up / down, 4-35 = buttons 0-31, 36 / 37 = slider 1 / 2, 38 = throttle
(Z), 39 / 40 = rudder. The starting `config/menudata.ini` binds analogue steering, RT throttle
(slider 1), LT brake (slider 2), X turbo, A signal, RB / LB gears. The menus take the joystick only
as "move" and "choose"; back (Esc), pause, Enter and the camera keys are keyboard only, hence the
Steam Input keys on the Deck.

## ogg-winmm

ogg-winmm v2025.01.16 answers the string command "open cdaudio" by passing `MCI_OPEN` on to the
real winmm with a NULL parameter block. Windows' winmm fails and the result is ignored; Wine's
writes the device ID back through the NULL pointer, an access violation inside `winmm.dll`.
`oggwinmm_fix.py` replaces that one call with `add esp,0x10 ; xor eax,eax` (the same stack, result 0).
