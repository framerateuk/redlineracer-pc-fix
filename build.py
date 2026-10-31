#!/usr/bin/env python3
"""Build a ready-to-run Redline Racer folder for modern PCs from your own CD.

Usage:
  python3 build.py DISC.cue|DISC.ccd --dgvoodoo DGVOODOO.zip --ogg-winmm OGG-WINMM.zip [--out DIR] [--windows]

  DISC          your Redline Racer CD (Criterion / Ubi Soft, 1998, the five-language European release) as .cue +
                .bin or .ccd + .img, with its audio tracks
  --dgvoodoo    dgVoodoo2 2.79.3 zip (or its unpacked folder)
  --ogg-winmm   ogg-winmm v2025.01.16 release zip (or folder)
  --out         where to create RedlineRacer/ (default: this folder)
  --windows     a folder for Windows only: the same game/ folder, without the Steam Deck launch script

Needs Python 3.8+ and an Ogg Vorbis encoder on the PATH: oggenc (vorbis-tools) or ffmpeg.
Nothing from the game is in this repository: every game file comes from your disc.
"""
import argparse, hashlib, os, shutil, struct, subprocess, sys, tempfile, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import disc, oggwinmm_fix, patch_exe

PATCHED_MD5 = "62663697cb4f5e71b189fe9323aaee61"
# What the installer copies for a full English Direct3D install: "Language Independant Files" + "Empty Directories",
# "English Files", and from "Basic Files" / "Direct3D Files" the files below (every file is read from the disc)
FOLDERS = ["bikes", "common", "misc", "Overlays", "RIDERS", "Sounds", "tracks", "UiData", "language/english"]
FILES = ["menudata.ini", "IFORCE2.dll", "D3d.ini"]
SPARE = [("rlr_D3d.exe", "rlr_D3d.exe"), ("rlr_3dfx.exe", "rlr_3dfx.exe"), ("3dfx.ini", "3dfx.ini"),
         ("selector.exe", "selector.exe"), ("language/english/text/README.TXT", "README-1998.TXT"),
         ("menudata.ini", "menudata-1998.ini"), ("UiData/Cursors/default.msk", "default.msk")]


def md5(data): return hashlib.md5(data).hexdigest()


def encoder():
    if shutil.which("oggenc"): return lambda wav, ogg: ["oggenc", "-Q", "-q", "7", wav, "-o", ogg]
    if shutil.which("ffmpeg"):
        return lambda wav, ogg: ["ffmpeg", "-loglevel", "error", "-y", "-i", wav, "-c:a", "libvorbis", "-q:a", "7", ogg]
    sys.exit("needs oggenc (vorbis-tools) or ffmpeg on the PATH to encode the soundtrack")


def rip(tracks, music):
    enc = encoder(); os.makedirs(music, exist_ok=True); n = 0
    with tempfile.TemporaryDirectory() as tmp:
        for t in tracks:
            if t.kind != "AUDIO": continue
            data = disc.audio(t)          # INDEX 01 to the next track's start: lengths match the disc's TOC
            wav = os.path.join(tmp, f"track{t.n:02d}.wav")
            with open(wav, "wb") as o:
                o.write(b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " +
                        struct.pack("<IHHIIHH", 16, 1, 2, 44100, 176400, 4, 16) + b"data" +
                        struct.pack("<I", len(data)) + data)
            subprocess.run(enc(wav, os.path.join(music, f"Track{t.n:02d}.ogg")), check=True); os.remove(wav)
            print(f"  Music/Track{t.n:02d}.ogg  {len(data) / 2352 / 75:6.1f} s"); n += 1
    if n != 6: sys.exit(f"expected 6 audio tracks (the game's music), found {n}: is the image missing them?")


def take(src, member):
    """Bytes of the file whose path ends with `member` (case-insensitive) in a zip or folder."""
    want = member.lower()
    if os.path.isdir(src):
        for d, _, fs in os.walk(src):
            for f in fs:
                p = os.path.join(d, f)
                if os.path.relpath(p, src).replace(os.sep, "/").lower().endswith(want): return open(p, "rb").read()
    else:
        with zipfile.ZipFile(src) as z:
            for name in z.namelist():
                if name.lower().endswith(want): return z.read(name)
    sys.exit(f"{member} not found in {src}")


def hide_cursor(path):
    """The menus draw UiData\\Cursors\\default.bmp where default.msk (an 8-bit 10x20 BMP) is not 0: a mask of
    zeros draws nothing. The mouse still works, unseen."""
    d = bytearray(open(path, "rb").read())
    off = struct.unpack_from("<I", d, 10)[0]; w, h = struct.unpack_from("<ii", d, 18); bpp = struct.unpack_from("<H", d, 28)[0]
    if d[:2] != b"BM" or (w, h, bpp) != (10, 20, 8): sys.exit(f"{path}: not the cursor mask expected")
    d[off:] = bytes(len(d) - off)
    open(path, "wb").write(d)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("disc"); ap.add_argument("--dgvoodoo", required=True); ap.add_argument("--ogg-winmm", required=True)
    ap.add_argument("--out", default=HERE); ap.add_argument("--windows", action="store_true")
    a = ap.parse_args()

    tracks = disc.tracks(a.disc)
    data = [t for t in tracks if t.kind != "AUDIO"]
    if not data: sys.exit("no data track in " + a.disc)
    dt = disc.DataTrack(data[0])
    entries = {p.lower(): (p, is_dir, l, s) for p, is_dir, l, s in dt.walk(joliet=True)}
    if "rlr_d3d.exe" not in entries: sys.exit("no rlr_D3d.exe on this CD: it isn't the Redline Racer disc the kit was made for")
    got = md5(dt.read_file(*entries["rlr_d3d.exe"][2:]))
    if got != patch_exe.MD5:
        sys.exit(f"this CD's rlr_D3d.exe is not the 9 July 1998 one the kit was made for (MD5 {got}); "
                 "nothing else is supported yet")
    winmm = oggwinmm_fix.patch(take(a.ogg_winmm, "winmm.dll"))    # before anything is written: the release must match

    pkg = os.path.join(os.path.abspath(a.out), "RedlineRacer"); game = os.path.join(pkg, "game")
    if os.path.exists(pkg): sys.exit(f"{pkg} already exists: move or delete it first")

    print("1/5 game files from the CD")
    roots = tuple(f.lower() + "/" for f in FOLDERS)
    for key, (p, is_dir, l, s) in entries.items():
        if not (key + "/").startswith(roots): continue
        dst = os.path.join(game, *p.split("/"))
        if is_dir: os.makedirs(dst, exist_ok=True)      # the empty folders too: the game saves into some
        else: dt.copy_file(l, s, dst)
    for f in FILES:
        dt.copy_file(*entries[f.lower()][2:], os.path.join(game, f))
    for f, dst in SPARE:
        dt.copy_file(*entries[f.lower()][2:], os.path.join(game, "_spare", dst))
    # Gameinst.ini as the installer writes it (the disc's has the developers' "CD=c:\redline\redline\"): with
    # CDInstall=FALSE the game reads everything from its own folder
    with open(os.path.join(game, "Gameinst.ini"), "wb") as f: f.write(b"CD=.\\\r\nLanguage=english\r\nCDInstall=FALSE\r\n")
    hide_cursor(os.path.join(game, "UiData", "Cursors", "default.msk"))

    print("2/5 exe patches")
    out = patch_exe.patch(dt.read_file(*entries["rlr_d3d.exe"][2:]))
    if md5(out) != PATCHED_MD5: sys.exit("patching gave an unexpected rlr_D3d.exe")
    open(os.path.join(game, "rlr_D3d.exe"), "wb").write(out)

    print("3/5 soundtrack")
    rip(tracks, os.path.join(game, "Music"))

    print("4/5 wrappers and settings")
    for member, name in [("MS/x86/DDraw.dll", "ddraw.dll"), ("MS/x86/D3DImm.dll", "d3dimm.dll")]:
        open(os.path.join(game, name), "wb").write(take(a.dgvoodoo, member))
    open(os.path.join(game, "winmm.dll"), "wb").write(winmm)
    for f in ("dgVoodoo.conf", "winmm.ini", "menudata.ini"):     # menudata.ini: the pad set-up
        shutil.copyfile(os.path.join(HERE, "config", f), os.path.join(game, f))

    print("5/5 Steam Deck launch script" if not a.windows else "5/5 done")
    if not a.windows:
        launch = os.path.join(pkg, "redline_launch.sh")
        shutil.copyfile(os.path.join(HERE, "steamdeck", "redline_launch.sh"), launch); os.chmod(launch, 0o755)
    print(f"\ndone: {pkg}  (see README.md)")


if __name__ == "__main__":
    main()
