"""Build the SharkyClips Helper store packages (1.2.74): Microsoft Edge Add-ons and Firefox Add-ons.

    python installer/build_extension.py            -> installer/dist/extension/
        sharkyclips-helper-<version>-edge.zip      upload at Partner Center (Edge Add-ons)
        sharkyclips-helper-<version>-firefox.zip   upload at addons.mozilla.org (Firefox Add-ons)
        sharkyclips-helper-<version>-source.zip    the readable source (AMO asks for it only when code is
                                                   minified; ours isn't, but it's there for review questions)

The packages hold the same scripts SharkyClips writes into its own browser profiles
(backend/sharkyclips/assist_ext/), the manifest from assist.store_manifest(), the logo as icons
and the 11 _locales. No config.js: a store copy pairs once with the 6-digit code from Settings.
Store texts, screenshots and the step-by-step guide: docs/extension-stores.md, docs/extension-store/.
Nothing here uploads anything.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sharkyclips import __version__, assist  # noqa: E402

OUT = ROOT / "installer" / "dist" / "extension"
FIXED_TIME = (2026, 1, 1, 0, 0, 0)  # same zip bytes for the same files (reproducible)


def files_for(target: str) -> dict[str, bytes]:
    src = assist._template()
    files: dict[str, bytes] = {}
    for name in assist.EXT_FILES:
        files[name] = (src / name).read_bytes()
    for d in sorted((src / "_locales").iterdir()):
        files[f"_locales/{d.name}/messages.json"] = (d / "messages.json").read_bytes()
    from PIL import Image

    logo = ROOT / "assets" / "icon" / "sharkyclips.png"
    import io

    with Image.open(logo) as im:
        im = im.convert("RGBA")
        for n in assist.EXT_ICON_SIZES:
            buf = io.BytesIO()
            im.resize((n, n), Image.Resampling.LANCZOS).save(buf, "PNG", optimize=True)
            files[f"icons/icon-{n}.png"] = buf.getvalue()
    files["manifest.json"] = (json.dumps(assist.store_manifest(__version__, target), indent=2, ensure_ascii=False)
                              + "\n").encode("utf-8")
    return files


def write_zip(path: Path, files: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, files[name])


def check(files: dict[str, bytes]) -> list[str]:
    """What the stores reject or what would break the "never click Post" promise."""
    problems = []
    m = json.loads(files["manifest.json"])
    if "config.js" in files:
        problems.append("config.js (an install's key) must never ship in a store package")
    for name, data in files.items():
        if name.endswith(".js"):
            text = data.decode("utf-8")
            for bad in ("eval(", "new Function(", "post_video_button\").click", "remote-debugging"):
                if bad in text:
                    problems.append(f"{name}: {bad}")
    for need in ("name", "version", "description", "icons", "manifest_version", "default_locale"):
        if need not in m:
            problems.append(f"manifest: no {need}")
    if any(h not in ("http://127.0.0.1/*", "http://localhost/*") for h in m["host_permissions"]):
        problems.append("host_permissions: only the local app")
    for loc in [k for k in files if k.endswith("messages.json")]:
        msgs = json.loads(files[loc])
        if len(msgs["description"]["message"]) > 132:
            problems.append(f"{loc}: description over 132 characters")
    return problems


def build() -> list[Path]:
    out = []
    for target in ("edge", "firefox"):
        files = files_for(target)
        problems = check(files)
        if problems:
            raise SystemExit("\n".join(problems))
        p = OUT / f"sharkyclips-helper-{__version__}-{target}.zip"
        write_zip(p, files)
        out.append(p)
    src = files_for("edge")
    src.pop("manifest.json")
    src["manifest.edge.json"] = (json.dumps(assist.store_manifest(__version__, "edge"), indent=2) + "\n").encode()
    src["manifest.firefox.json"] = (json.dumps(assist.store_manifest(__version__, "firefox"), indent=2) + "\n").encode()
    src["README.txt"] = (b"SharkyClips Helper source (not minified, no build step). The store zips hold these files\n"
                         b"with manifest.<target>.json renamed to manifest.json. Built by installer/build_extension.py\n"
                         b"from https://github.com/utkualsir/sharkyclips (backend/sharkyclips/assist_ext).\n")
    p = OUT / f"sharkyclips-helper-{__version__}-source.zip"
    write_zip(p, src)
    out.append(p)
    return out


if __name__ == "__main__":
    for p in build():
        print(f"{p.relative_to(ROOT)}  ({p.stat().st_size // 1024} KB)")
