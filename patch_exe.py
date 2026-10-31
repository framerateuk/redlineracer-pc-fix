#!/usr/bin/env python3
"""Patch Redline Racer's Direct3D exe (the disc's rlr_D3d.exe, 875,008 bytes, MD5 423fdb4f70f1a95a3607c1b4006ad886,
linked 9 Jul 1998, MSVC; Criterion Studios / Ubi Soft, version 1.00.000) into a copy.

  patch_exe.py <rlr_D3d.exe> <out.exe>   write the patched exe (refuses, writes nothing, on any unexpected byte)
  patch_exe.py --check-caves             re-assemble caves.s with clang and compare with CAVE below

New code (caves.s, assembled bytes in CAVE) goes into a section the patch adds: ".rdeck", VA 0x556000, 0x1000 bytes
at file offset 0xd5a00 (the end of the file, after the linker's CodeView block that follows .reloc), readable /
writable / executable; its variables from 0x556c00. The section table had room for a ninth entry (it ended at 0x2b8,
the first section starts at 0x400); SizeOfImage 0x156000 -> 0x157000. The exe has no checksum and loads at its
0x400000 base; the header now also says "relocations stripped", so no loader ever moves it.

Each patch is described by what it hooks and how it was found, so it can be found again in another build of the
engine (Suzuki Alstare Extreme Racing, which has its own kit). Addresses are this exe's.

  rdeck       the section (above) with the code of caves.s.
  nocd        the CD check. Found from the "Could not find files on CD / Please reinsert the Red Line Racer CD"
              MessageBoxA (0x41dcd6, string 0x4b36dc): its caller 0x41dcb0 first calls 0x41da30, which tries every
              drive C: to Y: ("%c:\\" + GetDiskFreeSpaceA: a drive with 0 free clusters, i.e. a CD) for
              "common\\normal.dff" (or "rlr\\common\\normal.dff") that opens for reading but not for writing.
              Wine reports a folder's free space as the host disk's, so no fake drive can pass (as Sub Culture,
              Criterion 1997). 0x41da30 now returns 1 at once ("mov eax, 1; ret"). The game never reads data from
              the CD: with Gameinst.ini's CDInstall=FALSE everything comes from the exe's folder (0x43c1f0), and the
              CD path itself (Gameinst.ini CD=) is only checked for being there.
  pad         the joystick. The game reads it in one function, 0x418b80 (found from its "DirectInputCreate 5.0
              FAILED - no joystick support" set-up and the vtable calls Poll [+0x64] and GetDeviceState(0x50 =
              sizeof DIJOYSTATE) [+0x24]): it fills a 9-dword struct (X Y Z Rx Ry Rz as floats -1..1, two sliders
              0..1, 32 button bits; no POV) that the input pump 0x443ed0 hands to the current input handler as
              event 0x16 every frame. The race's handler (0x43de80) copies it to 0x4e36b8, where the control code
              0x452010 turns it into the eight controls by menudata.ini's bindings (docs/TECHNICAL.md, "Pad"). Under Proton an
              Xbox pad's triggers share DirectInput's Z axis (both held = neither) and are not sliders, so the
              pump's call (0x443ee8) now goes to joyread, which writes the struct from XInput: left stick X / Y,
              RT / LT as the two sliders, the buttons; without an XInput pad the game's own read runs. The
              Controls screen's own read (0x431179, button capture) goes to joyraw (all buttons). The pump's test
              "a joystick was found" (0x443ed3, "mov eax, [0x50bb9c]") calls padcount: also true with an XInput
              pad DirectInput did not list.
  logoskip    the start-up logos (Criterion, Ubi Soft; Imagineer in Japanese: .pat animations + .wav, 0x4334d0) end on
              a typed key ("call 0x435510" = pop the typed-keys queue, at 0x43358f and 0x4335f2, found from the
              "%sMISC\\%s.WAV" / "CRIT" / "UBI" strings at 0x4334f9 / 0x433706): those calls go to logokey, which
              also ends them on A, B, X, Y, View or Start newly pressed. (There are no movies in this game.)
  nocursor    the window class (RegisterClassA "RedLine", 0x416bb4) had LoadCursorA(0, IDC_ARROW) as its cursor
              (0x416b8b, 12 bytes "push 0x7f00; push esi; call [LoadCursorA]"): now "xor eax, eax" (no class
              cursor). The game already answers WM_SETCURSOR with SetCursor(NULL) (0x416eab). The menus' own
              drawn pointer (UiData\\Cursors\\default.bmp / .msk) is made transparent by assemble.sh, not here.
  noweb       the main menu's web-site button (0x4247aa, misc\\redline.url) and the F1 help (0x42a82e,
              help\\index.htm through misc\\help.url) start a browser with ShellExecuteA; on the Deck that would
              open one over Game Mode. Both calls ("call [ShellExecuteA]", 6 bytes) are now "add esp, 0x18;
              push 0x21; pop eax": the 6 arguments dropped, result 33 (success, so no error box).

Not patched (docs/TECHNICAL.md): no registry use at all (the exe imports no Reg* function); no frame
limiter or busy wait (the physics take the frame time from timeGetTime, 0x43e6c0, in 10 ms sub-steps; dgVoodoo's
vsync and FPSLimit hold 60 frames a second); 640x480 x 16 is hard-wired (0x4169e0).
"""
import hashlib, os, struct, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE, MD5 = 875008, "423fdb4f70f1a95a3607c1b4006ad886"
DELTA = 0x400c00                       # .text (VA 0x401000, file offset 0x400): file offset = VA - 0x400c00
def T(va):
    assert 0x401000 <= va < 0x4ac74b, hex(va)
    return va - DELTA

def rel32(src, dst, op):               # e8 / e9 at src (5 bytes) -> dst
    return bytes([op]) + (dst - (src + 5)).to_bytes(4, "little", signed=True)

SECT_VA, SECT_RVA, SECT_OFF, SECT_SIZE = 0x556000, 0x156000, 0xd5a00, 0x1000
CAVE_VA = SECT_VA
CAVE = bytes.fromhex(
    "b801000000eb0231c06089c58b742428e82a01000085c0740ce80d00000061b801000000c361e9552becff8b1d086c55"
    "00a10c6c5500e8c1000000f6c3047406ddd8d9e8d9e0f6c3087404ddd8d9e8d91ea1106c5500e8a1000000d9e0f6c301"
    "7406ddd8d9e8d9e0f6c3027404ddd8d9e8d95e04c746080000803fa1146c5500e877000000d95e0ca1186c5500e86a00"
    "0000d9e0d95e10c7461400000000a1206c5500e883000000d95e18a11c6c5500e876000000d95e1c31c9bf7062550031"
    "d20fb7045785c374030fabd14283fa0a72ef89c883e0018b15246c5500a3246c550085ed7412813df4655100d8894200"
    "7506f7d221d089c1894e20c389c19931d029d02da00f00007f03d9eec33d5f7000007e05b85f70000050db0424d80d84"
    "6255005885c97902d9e0c383f8087d03d9eec350db0424d80d8862550058c360833d046c550000753cc705046c550001"
    "000000bea0625500bb0300000056ff15c873540085c07417688c62550050ff159c73540085c07407a3006c5500eb0683"
    "c6104b75d8833d006c550000747531db68406c550053ff15006c550085c074084383fb0472eaeb5b0fb705446c5500a3"
    "086c55000fb605466c5500a31c6c55000fb605476c5500a3206c55000fbf05486c5500a30c6c55000fbf054a6c5500a3"
    "106c55000fbf054c6c5500a3146c55000fbf054e6c5500a3186c550061b801000000c331c0a3086c5500a30c6c5500a3"
    "106c5500a3146c5500a3186c5500a31c6c5500a3206c55006131c0c3a19cbb500085c07f05e805ffffffc3e8d0f2edff"
    "84c0752b60e8f5feffff85c07420a1086c55002530f000008b0d286c5500a3286c5500f7d121c87405c644241c0d61c3"
    "001000200040008000010002200010004000800079cd11388180803b58496e7075744765745374617465000f1f440000"
    "78696e707574315f342e646c6c00669078696e707574315f332e646c6c00669078696e707574395f315f302e646c6c00")
SYM = {"joyread": 0x000, "joyraw": 0x007, "padcount": 0x22c, "logokey": 0x23b}   # labels of caves.s
def C(name): return CAVE_VA + SYM[name]

def build():
    """(va, old bytes, new bytes) for every patch site."""
    e = []
    # nocd: "sub esp, 0x118" at the CD check's entry -> "mov eax, 1; ret"
    e.append((0x41da30, bytes.fromhex("81ec18010000"), bytes.fromhex("b801000000c3")))
    # pad: the pump's "mov eax, [0x50bb9c]" (joystick count) -> call padcount; its "call 0x418b80" -> call joyread;
    # the Controls screen's "call 0x418b80" -> call joyraw
    e.append((0x443ed3, bytes.fromhex("a19cbb5000"), rel32(0x443ed3, C("padcount"), 0xe8)))
    e.append((0x443ee8, rel32(0x443ee8, 0x418b80, 0xe8), rel32(0x443ee8, C("joyread"), 0xe8)))
    e.append((0x431179, rel32(0x431179, 0x418b80, 0xe8), rel32(0x431179, C("joyraw"), 0xe8)))
    # logoskip: the logo loops' "call 0x435510" (typed-keys queue) -> call logokey
    for va in (0x43358f, 0x4335f2):
        e.append((va, rel32(va, 0x435510, 0xe8), rel32(va, C("logokey"), 0xe8)))
    # nocursor: "push 0x7f00; push esi; call [LoadCursorA]" -> "xor eax, eax" (hCursor = NULL)
    e.append((0x416b8b, bytes.fromhex("68007f000056ff1548755400"), bytes.fromhex("31c0") + b"\x90" * 10))
    # noweb: "call [ShellExecuteA]" -> "add esp, 0x18; push 0x21; pop eax"
    for va in (0x4247aa, 0x42a82e):
        e.append((va, bytes.fromhex("ff15bc745400"), bytes.fromhex("83c4186a2158")))
    return e

def add_section(data):
    lfanew = struct.unpack_from("<I", data, 0x3c)[0]
    nsec = struct.unpack_from("<H", data, lfanew + 6)[0]
    optsize = struct.unpack_from("<H", data, lfanew + 20)[0]
    sh = lfanew + 24 + optsize + 40 * nsec
    if nsec != 8 or sh != 0x2b8 or any(data[sh:sh + 40]) or len(data) != SECT_OFF:
        sys.exit("unexpected PE header; nothing written")
    struct.pack_into("<8sIIIIIIHHI", data, sh, b".rdeck", SECT_SIZE, SECT_RVA, SECT_SIZE, SECT_OFF, 0, 0, 0, 0,
                     0xE0000060)       # code | initialised data | execute | read | write
    struct.pack_into("<H", data, lfanew + 6, nsec + 1)
    chars = struct.unpack_from("<H", data, lfanew + 22)[0]
    struct.pack_into("<H", data, lfanew + 22, chars | 1)     # IMAGE_FILE_RELOCS_STRIPPED
    if struct.unpack_from("<I", data, lfanew + 24 + 56)[0] != SECT_RVA: sys.exit("unexpected SizeOfImage")
    struct.pack_into("<I", data, lfanew + 24 + 56, SECT_RVA + SECT_SIZE)
    data += CAVE + bytes(SECT_SIZE - len(CAVE))

def elf_text(path):                    # .text bytes and label offsets of an i386 ELF object (no relocations)
    d = open(path, "rb").read()
    shoff = struct.unpack_from("<I", d, 0x20)[0]; shentsize, shnum, shstrndx = struct.unpack_from("<HHH", d, 0x2e)
    secs = [struct.unpack_from("<10I", d, shoff + i * shentsize) for i in range(shnum)]
    names = [d[secs[shstrndx][4] + x[0]:].split(b"\0")[0].decode() for x in secs]
    if any(n.startswith(".rel") and x[5] for n, x in zip(names, secs)): sys.exit("caves.o has relocations")
    ti = names.index(".text"); text = d[secs[ti][4]:secs[ti][4] + secs[ti][5]]; syms = {}
    for x in secs:
        if x[1] != 2: continue                                   # SHT_SYMTAB
        strs = secs[x[6]]
        for i in range(x[5] // 16):
            nm, val, size, info, oth, shn = struct.unpack_from("<IIIBBH", d, x[4] + 16 * i)
            if shn == ti: syms[d[strs[4] + nm:].split(b"\0")[0].decode()] = val
    return text, syms

ENTRIES = ("joyread", "joyraw", "padcount", "logokey")
def check_caves():
    with tempfile.TemporaryDirectory() as t:
        o = os.path.join(t, "caves.o")
        subprocess.run(["clang", "-target", "i386-pc-linux-gnu", "-c", os.path.join(HERE, "caves.s"), "-o", o], check=True)
        text, syms = elf_text(o)
    ok = text == CAVE and all(syms.get(k) == SYM.get(k) for k in ENTRIES)
    print("caves.s matches CAVE" if ok else "caves.s differs from CAVE / SYM: update patch_exe.py")
    if not ok:
        print("CAVE =", text.hex()); print("SYM =", {k: hex(syms[k]) for k in ENTRIES})
    return ok

def patch(data, label="rlr_D3d.exe"):
    """Returns the patched exe; exits on any unexpected byte."""
    data = bytearray(data)
    if len(data) != SIZE or hashlib.md5(data).hexdigest() != MD5:
        sys.exit(f"{label}: not the disc's rlr_D3d.exe (size {SIZE}, MD5 {MD5}); nothing written")
    assert 0 < len(CAVE) < 0xc00, "CAVE empty or running into the variables at 0x556c00"
    edits = build()
    for va, old, new in edits:
        off = T(va)
        if bytes(data[off:off + len(old)]) != old or len(old) != len(new):
            sys.exit(f"unexpected bytes at VA {va:#x}; nothing written")
    for va, old, new in edits:
        data[T(va):T(va) + len(new)] = new
    add_section(data)
    print(f"  rdeck nocd pad logoskip nocursor noweb ({len(edits)} edits)")
    return bytes(data)

def main(src, dst):
    data = patch(open(src, "rb").read(), src)
    tmp = dst + ".tmp"
    open(tmp, "wb").write(data)
    os.replace(tmp, dst)
    print(f"{dst}: MD5 {hashlib.md5(data).hexdigest()}")

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--check-caves": sys.exit(0 if check_caves() else 1)
    if len(sys.argv) != 3: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
