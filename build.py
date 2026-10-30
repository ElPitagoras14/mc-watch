"""Build the Windows executable: `uv run build.py` -> dist/mc-watch.exe.

One file, no console, with an icon and a version resource.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UI = ROOT / "mc_watch" / "ui"
NAME = "mc-watch"

# What PyInstaller pulls in by default and this app never uses. Pillow is the bulk: the tray icon
# only draws shapes and text, so the image codecs are dead weight. `PIL._imagingft` stays: the
# icon draws the online count with FreeType.
UNUSED = (
    "PIL.AvifImagePlugin",
    "PIL._avif",
    "PIL.WebPImagePlugin",
    "PIL._webp",
    "PIL.ImageCms",
    "PIL._imagingcms",
    "PIL.ImageTk",
    "tkinter",
    "unittest",
    "pydoc",
    "doctest",
)

LAUNCHER = """\
import sys

from mc_watch.__main__ import main

sys.exit(main())
"""


def version() -> str:
    sys.path.insert(0, str(ROOT))
    from mc_watch import __version__

    return __version__


def version_file(path: Path, ver: str) -> Path:
    nums = tuple(([int(part) for part in ver.split(".")] + [0] * 4)[:4])
    path.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040A04B0', [
      StringStruct('CompanyName', 'mc-watch'),
      StringStruct('FileDescription', 'mc-watch: servidores de Minecraft en la bandeja'),
      StringStruct('FileVersion', '{ver}'),
      StringStruct('InternalName', '{NAME}'),
      StringStruct('OriginalFilename', '{NAME}.exe'),
      StringStruct('ProductName', 'mc-watch'),
      StringStruct('ProductVersion', '{ver}')])]),
    VarFileInfo([VarStruct('Translation', [0x040A, 1200])])
  ]
)
""",
        "utf-8",
    )
    return path


def main() -> int:
    import PyInstaller.__main__  # pyright: ignore[reportMissingTypeStubs]

    ver = version()
    work = Path(tempfile.mkdtemp(prefix="mc-watch-build-"))
    launcher = work / "mc_watch_launcher.py"
    launcher.write_text(LAUNCHER, "utf-8")

    args = [
        str(launcher),
        "--name",
        NAME,
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--paths",
        str(ROOT),
        "--distpath",
        str(ROOT / "dist"),
        "--workpath",
        str(work / "build"),
        "--specpath",
        str(work),
        "--add-data",
        f"{UI}{os.pathsep}mc_watch/ui",
        "--version-file",
        str(version_file(work / "version.txt", ver)),
        # The browser preview does not ship in the executable.
        "--exclude-module",
        "mc_watch.preview",
        *[arg for module in UNUSED for arg in ("--exclude-module", module)],
        "--collect-submodules",
        "mc_watch",
        "--collect-submodules",
        "desktop_notifier",
        # dnspython loads its record types dynamically and the SRV lookup needs them.
        "--collect-submodules",
        "dns.rdtypes",
    ]

    try:
        from mc_watch.tray import app_icon

        ico = work / f"{NAME}.ico"
        app_icon().save(ico, sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
        args += ["--icon", str(ico)]
    except Exception as error:
        # Without an icon the executable is still useful; not being able to build it is not.
        print(f"AVISO: no se pudo generar el icono ({error}); el .exe sale sin icono")

    print(f"Construyendo {NAME} {ver}…")
    try:
        PyInstaller.__main__.run(args)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    out = ROOT / "dist" / f"{NAME}.exe"
    print(f"Listo: {out} ({out.stat().st_size / 1_000_000:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
