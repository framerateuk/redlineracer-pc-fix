# Redline Racer (rlr_D3d.exe, the disc's Direct3D exe, 875,008 bytes, built Jul 1998, MSVC; Criterion Studios /
# Ubi Soft): new code for patch_exe.py. It goes into a section patch_exe.py adds to the exe, ".rdeck" at VA 0x556000
# (file offset 0xd5a00, the end of the file, 0x1000 bytes, readable / writable / executable): this code from
# 0x556000, its variables from 0x556c00 (zero when the exe loads). The exe always loads at its 0x400000 base (no
# dynamic-base flag; the patch also marks it "relocations stripped"), so absolute addresses are used throughout.
#
# Assembled with Apple clang (integrated assembler):
#   clang -target i386-pc-linux-gnu -c caves.s -o caves.o
# patch_exe.py carries the resulting bytes (CAVE) and checks them against this file when clang is around
# (patch_exe.py --check-caves). docs/TECHNICAL.md explains each routine.
#
# Reuse (Suzuki Alstare Extreme Racing, the same Criterion engine): readpad / axisf / trigf / btnmap are
# self-contained (XInput found at the first call through LoadLibraryA / GetProcAddress; nothing else of the game
# is touched). joyfill writes the game's own joystick reading (the 9-dword struct its DirectInput joystick read
# 0x418b80 fills, docs/TECHNICAL.md "Pad"); the game addresses it needs are the .set lines under "game" below: find them
# again in the other exe by their code patterns, and re-check the IAT slots.
#
# Lesson kept from Speedster (23 Oct 2026): never keep a value in ecx / edx across an API call (Proton's
# timeGetTime and friends change them). Every routine here saves what it uses with pushad / popad, and keeps
# values across API calls only in ebx / esi / edi / ebp or memory.
.intel_syntax noprefix
.set BASE, 0x556000

# imports used (IAT slots of rlr_D3d.exe)
.set GetProcAddress,   0x54739c
.set LoadLibraryA,     0x5473c8

# game
.set JOYREAD,  0x418b80              # int JoyRead(int device, JOYSTATE *out): the DirectInput joystick read
                                     #   (Poll + GetDeviceState(DIJOYSTATE) -> 6 axes, 2 sliders as floats, 32
                                     #   button bits); device 1 = the first joystick
.set JOYCOUNT, 0x50bb9c              # joysticks DirectInput found at start-up (the pump reads the pad only if > 0)
.set INHANDLER, 0x5165f4             # the current input-event handler (the menus', the race's, ...)
.set MENUHANDLER, 0x4289d8           # the front-end menus' handler
.set KEYPOP,   0x435510              # al = next character from the typed-keys queue (0 = none)

# our variables (.rdeck from 0x556c00, zero at load)
.set XGS,     0x556c00               # XInputGetState (0 = no XInput DLL)
.set XINIT,   0x556c04               # 1 once readpad has looked for XInput
.set PB,      0x556c08               # the pad as readpad last read it: XInput wButtons (DPAD_UP 1, DOWN 2, LEFT 4,
.set PLX,     0x556c0c               #   RIGHT 8, START 0x10, BACK 0x20, L3 0x40, R3 0x80, LB 0x100, RB 0x200,
.set PLY,     0x556c10               #   A 0x1000, B 0x2000, X 0x4000, Y 0x8000); left stick X / Y (signed, up +)
.set PRX,     0x556c14               #   right stick X / Y
.set PRY,     0x556c18
.set PLT,     0x556c1c               #   left / right trigger 0..255
.set PRT,     0x556c20
.set MENUA,   0x556c24               # joyfill: A was down at the previous read (menus see A only when newly pressed)
.set LOGOPREV, 0x556c28              # logokey: pad buttons down at the previous look
.set XS,      0x556c40               # an XINPUT_STATE (16 bytes)

.set DZ,      4000                   # stick dead zone (of 32767): about 12 %
.set TDZ,     8                      # trigger dead zone (of 255)

.macro PUSHI v                       # push imm32 (clang's intel syntax would make "push offset" 16-bit)
  .byte 0x68
  .long \v
.endm

.text
start:

# ---------------------------------------------------------------------------------------------------------------
# joyread (patch pad): the input pump (0x443ed0, every frame in the menus, in a race and in the logo / CD-check
# loops) reads the joystick with "push out; push 1; call JoyRead" (0x443ee8) and hands the reading to the current
# event handler as event 0x16. The call now comes here; same arguments (cdecl), same result (eax 1 = a reading).
# With an XInput pad the whole reading is written from it (joyfill), in the menus with only A as a button and only
# when newly pressed (the menus take any joystick button as "choose" and repeat it while it is held); without one,
# the game's own DirectInput read runs as before (jmp JOYREAD: the stack is as the game left it).
joyread:
  mov eax, 1
  jmp joycommon

# joyraw (patch pad): the Controls screen's own read (0x431179, which takes the button bits for "press a button
# to bind"): the same reading with every button.
joyraw:
  xor eax, eax
joycommon:
  pushad
  mov ebp, eax                       # 1 = filter the buttons in the menus
  mov esi, dword ptr [esp + 0x28]    # JOYSTATE * (pushad 0x20, return address, device, out)
  call readpad
  test eax, eax
  jz 90f
  call joyfill
  popad
  mov eax, 1
  ret
90:
  popad
  .byte 0xe9                         # jmp JOYREAD: the game's own read
  .long JOYREAD - (BASE + (1f - start))
1:

# joyfill: esi = the game's JOYSTATE, ebp = 1 to filter buttons in the menus. From readpad's reading:
#   +0x00 X, +0x04 Y  the left stick (-1..1, DirectInput sense: right / down positive), dead zone DZ; the D-pad
#                     overrides with full deflection (on the Deck Steam Input turns the D-pad into arrow keys)
#   +0x08 Z           1.0: the game's "THROTTLE" binding reads (1 - Z) / 2, so 0 at rest; nothing else uses Z
#   +0x0c Rx, +0x10 Ry  the right stick (the game has no binding for them)
#   +0x14 Rz          0 (the game's "RUDDER" bindings: never move)
#   +0x18 slider 1    RT, 0..1   } separate analogue triggers (DirectInput puts an Xbox pad's triggers on one
#   +0x1c slider 2    LT, 0..1   } shared axis under Proton: both held = neither)
#   +0x20 buttons     bit 0 A, 1 B, 2 X, 3 Y, 4 LB, 5 RB, 6 View, 7 Start, 8 L3, 9 R3 (the game's "JOY BUTTON
#                     n" = binding parameter 4 + n). In the menus (ebp = 1, INHANDLER = MENUHANDLER): bit 0 only,
#                     A newly pressed.
joyfill:
  mov ebx, dword ptr [PB]
  mov eax, dword ptr [PLX]
  call axisf
  test bl, 4
  jz 1f
  fstp st(0)
  fld1
  fchs
1:
  test bl, 8
  jz 2f
  fstp st(0)
  fld1
2:
  fstp dword ptr [esi]
  mov eax, dword ptr [PLY]
  call axisf
  fchs                               # XInput up = +, DirectInput up = -
  test bl, 1
  jz 3f
  fstp st(0)
  fld1
  fchs
3:
  test bl, 2
  jz 4f
  fstp st(0)
  fld1
4:
  fstp dword ptr [esi + 4]
  mov dword ptr [esi + 8], 0x3f800000
  mov eax, dword ptr [PRX]
  call axisf
  fstp dword ptr [esi + 0xc]
  mov eax, dword ptr [PRY]
  call axisf
  fchs
  fstp dword ptr [esi + 0x10]
  mov dword ptr [esi + 0x14], 0
  mov eax, dword ptr [PRT]
  call trigf
  fstp dword ptr [esi + 0x18]
  mov eax, dword ptr [PLT]
  call trigf
  fstp dword ptr [esi + 0x1c]
  xor ecx, ecx                       # buttons
  .byte 0xbf                         # mov edi, btnmap
  .long A_BTNMAP
  xor edx, edx
5:
  movzx eax, word ptr [edi + edx*2]
  test ebx, eax
  jz 6f
  bts ecx, edx
6:
  inc edx
  cmp edx, 10
  jb 5b
  mov eax, ecx
  and eax, 1                         # A now
  mov edx, dword ptr [MENUA]
  mov dword ptr [MENUA], eax
  test ebp, ebp
  jz 8f
  cmp dword ptr [INHANDLER], MENUHANDLER
  jne 8f
  not edx
  and eax, edx                       # A newly pressed
  mov ecx, eax
8:
  mov dword ptr [esi + 0x20], ecx
  ret

# axisf: eax = a stick axis (-32768..32767) -> st(0) = -1..1, 0 inside the dead zone DZ and scaled from its edge
# (no jump at the edge). Changes eax, ecx, edx.
axisf:
  mov ecx, eax
  cdq
  xor eax, edx
  sub eax, edx                       # |value|
  sub eax, DZ
  jg 1f
  fldz
  ret
1:
  cmp eax, 32767 - DZ
  jle 2f
  mov eax, 32767 - DZ
2:
  push eax
  fild dword ptr [esp]
  fmul dword ptr [A_AXSCALE]
  pop eax
  test ecx, ecx
  jns 3f
  fchs
3:
  ret

# trigf: eax = a trigger (0..255) -> st(0) = 0..1, 0 below TDZ. Changes eax.
trigf:
  cmp eax, TDZ
  jge 1f
  fldz
  ret
1:
  push eax
  fild dword ptr [esp]
  fmul dword ptr [A_TRSCALE]
  pop eax
  ret

# ---------------------------------------------------------------------------------------------------------------
# readpad: the pad into PB / PLX / PLY / PRX / PRY / PLT / PRT (XInput layout): XInput pad 0..3, the first
# connected one. The first call looks for XInputGetState in xinput1_4.dll, else xinput1_3.dll, else
# xinput9_1_0.dll (Proton has all three; Windows 8+ has 1_4 and 9_1_0; the exe imports none of them).
# Returns eax = 1 with a reading, 0 without (no XInput, no pad). Keeps every other register.
readpad:
  pushad
  cmp dword ptr [XINIT], 0
  jne 10f
  mov dword ptr [XINIT], 1
  .byte 0xbe                         # mov esi, the three names (16 bytes each)
  .long A_XINPUT
  mov ebx, 3
2:
  push esi
  call dword ptr [LoadLibraryA]
  test eax, eax
  jz 3f
  PUSHI BASE + (s_xgs - start)
  push eax
  call dword ptr [GetProcAddress]
  test eax, eax
  jz 3f
  mov dword ptr [XGS], eax
  jmp 10f
3:
  add esi, 16
  dec ebx
  jnz 2b
10:
  cmp dword ptr [XGS], 0
  je 99f
  xor ebx, ebx                       # pad index
11:
  PUSHI XS
  push ebx
  call dword ptr [XGS]
  test eax, eax
  jz 12f
  inc ebx
  cmp ebx, 4
  jb 11b
  jmp 99f
12:
  movzx eax, word ptr [XS + 4]
  mov dword ptr [PB], eax
  movzx eax, byte ptr [XS + 6]
  mov dword ptr [PLT], eax
  movzx eax, byte ptr [XS + 7]
  mov dword ptr [PRT], eax
  movsx eax, word ptr [XS + 8]
  mov dword ptr [PLX], eax
  movsx eax, word ptr [XS + 10]
  mov dword ptr [PLY], eax
  movsx eax, word ptr [XS + 12]
  mov dword ptr [PRX], eax
  movsx eax, word ptr [XS + 14]
  mov dword ptr [PRY], eax
  popad
  mov eax, 1
  ret
99:
  xor eax, eax
  mov dword ptr [PB], eax
  mov dword ptr [PLX], eax
  mov dword ptr [PLY], eax
  mov dword ptr [PRX], eax
  mov dword ptr [PRY], eax
  mov dword ptr [PLT], eax
  mov dword ptr [PRT], eax
  popad
  xor eax, eax
  ret

# ---------------------------------------------------------------------------------------------------------------
# padcount (patch pad): the pump reads the joystick only when DirectInput found one at start-up
# ("mov eax, [JOYCOUNT]; test eax, eax; ... jle skip", 0x443ed3). That load is now "call padcount": the count, or
# 1 when there is none but an XInput pad reads (a pad Proton's DirectInput did not list still works).
padcount:
  mov eax, dword ptr [JOYCOUNT]
  test eax, eax
  jg 1f
  call readpad
1:
  ret

# ---------------------------------------------------------------------------------------------------------------
# logokey (patch logoskip): the Criterion / Ubi Soft (Japanese: Imagineer) logo loops (0x4334d0) end when a key is
# typed ("call KEYPOP; test al, al", 0x43358f and 0x4335f2). Those calls come here: the typed key as before, or
# Enter (0x0d) when A, B, X, Y, View or Start on the pad is newly pressed.
logokey:
  .byte 0xe8                         # call KEYPOP
  .long KEYPOP - (BASE + (1f - start))
1:
  test al, al
  jnz 9f
  pushad
  call readpad
  test eax, eax
  jz 8f
  mov eax, dword ptr [PB]
  and eax, 0xf030                    # A B X Y View Start
  mov ecx, dword ptr [LOGOPREV]
  mov dword ptr [LOGOPREV], eax
  not ecx
  and eax, ecx                       # newly pressed
  jz 8f
  mov byte ptr [esp + 0x1c], 0x0d    # al (pushad's eax slot) = Enter
8:
  popad
9:
  ret

# ---------------------------------------------------------------------------------------------------------------
  .p2align 2
btnmap:    .short 0x1000, 0x2000, 0x4000, 0x8000, 0x0100, 0x0200, 0x0020, 0x0010, 0x0040, 0x0080
                                     # game buttons 0-9 (A B X Y LB RB View Start L3 R3) as XInput bits
  .p2align 2
f_axscale: .long 0x3811cd79          # 1 / (32767 - DZ) = 1 / 28767
f_trscale: .long 0x3b808081          # 1 / 255
s_xgs:     .asciz "XInputGetState"
  .p2align 4
s_xinput:  .asciz "xinput1_4.dll"
  .p2align 4
           .asciz "xinput1_3.dll"
  .p2align 4
           .asciz "xinput9_1_0.dll"
.set A_AXSCALE, BASE + (f_axscale - start)
.set A_TRSCALE, BASE + (f_trscale - start)
.set A_XINPUT, BASE + (s_xinput - start)
.set A_BTNMAP, BASE + (btnmap - start)
