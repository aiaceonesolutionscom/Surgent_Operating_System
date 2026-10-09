"""Turn the hero's scroll-scrubbed videos into WebP frame sequences.

Why: scrubbing an <video> by assigning currentTime makes the browser decode from
the nearest keyframe on EVERY step, asynchronously, so scrolling feels laggy and
frames are skipped; the 1280x720 H.264 is also upscaled by the browser's cheap
filter. A pre-extracted image sequence drawn to a <canvas> has none of that: a
frame is just a bitmap, picked straight from the scroll position.

    python frontend/scripts/build-scroll-frames.py          (needs Pillow + ffmpeg)

ffmpeg is taken from PATH, or from the `imageio-ffmpeg` pip package.
Output (committed): public/lets-scroll/frames/<scene>/NNN.webp (desktop),
public/lets-scroll/frames/<scene>-m/NNN.webp (phones, portrait crop), and
src/components/hero/frames.manifest.json (frame counts for the engine).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets-src" / "lets-scroll"   # source clips (not deployed)
PUBLIC = ROOT / "public" / "lets-scroll"
OUT = PUBLIC / "frames"
MANIFEST = ROOT / "src" / "components" / "hero" / "frames.manifest.json"

SCENES = ["reception", "booking", "care", "growth"]
FPS = 12  # the engine blends neighbouring frames, so 12 is plenty and halves the download

DESKTOP = {"size": (1440, 810), "quality": 80}
# Phones show a tall slice of a landscape video, so only the centre 9:16 column
# is ever visible - ship just that, at a size a phone can use.
MOBILE = {"size": (540, 960), "quality": 76, "crop_aspect": 9 / 16}

UNSHARP = ImageFilter.UnsharpMask(radius=1.1, percent=55, threshold=2)


def find_ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg not found: install it, or `pip install imageio-ffmpeg`")


def extract(ffmpeg: str, clip: Path, dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(clip), "-vf", f"fps={FPS}", "-start_number", "0", str(dest / "%03d.png")],
        check=True,
    )
    return sorted(dest.glob("*.png"))


def prepare(img: Image.Image, spec: dict) -> Image.Image:
    img = img.convert("RGB")
    aspect = spec.get("crop_aspect")
    if aspect:
        w, h = img.size
        crop_w = round(h * aspect)
        left = (w - crop_w) // 2
        img = img.crop((left, 0, left + crop_w, h))
    return img.resize(spec["size"], Image.LANCZOS).filter(UNSHARP)


def build(ffmpeg: str, scene: str, clip: Path, out_dir: Path, spec: dict) -> int:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as tmp:
        frames = extract(ffmpeg, clip, Path(tmp))
        for i, frame in enumerate(frames):
            prepare(Image.open(frame), spec).save(out_dir / f"{i:03d}.webp", "WEBP", quality=spec["quality"], method=5)
    return len(frames)


def main() -> None:
    ffmpeg = find_ffmpeg()
    manifest: dict[str, dict] = {}
    for scene in SCENES:
        desktop_clip = SRC / f"{scene}.mp4"
        mobile_clip = SRC / f"{scene}-mobile.mp4"
        if not desktop_clip.exists():
            sys.exit(f"missing {desktop_clip}")
        count = build(ffmpeg, scene, desktop_clip, OUT / scene, DESKTOP)
        count_m = build(ffmpeg, scene, mobile_clip if mobile_clip.exists() else desktop_clip, OUT / f"{scene}-m", MOBILE)
        size = sum(f.stat().st_size for f in (OUT / scene).glob("*.webp"))
        size_m = sum(f.stat().st_size for f in (OUT / f"{scene}-m").glob("*.webp"))
        print(f"{scene:10} desktop {count} frames {size/1e6:5.1f} MB | mobile {count_m} frames {size_m/1e6:4.1f} MB")
        manifest[scene] = {
            "desktop": {"dir": f"/lets-scroll/frames/{scene}", "count": count, "width": DESKTOP["size"][0], "height": DESKTOP["size"][1]},
            "mobile": {"dir": f"/lets-scroll/frames/{scene}-m", "count": count_m, "width": MOBILE["size"][0], "height": MOBILE["size"][1]},
        }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("wrote", MANIFEST.relative_to(ROOT))


if __name__ == "__main__":
    main()
