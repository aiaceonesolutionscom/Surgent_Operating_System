"""Turn the hero's scroll-scrubbed videos into WebP frame sequences.

Why: scrubbing an <video> by assigning currentTime makes the browser decode from
the nearest keyframe on EVERY step, asynchronously, so scrolling feels laggy and
frames are skipped; the 1280x720 H.264 is also upscaled by the browser's cheap
filter. A pre-extracted image sequence drawn to a <canvas> has none of that: a
frame is just a bitmap, picked straight from the scroll position.

Every source frame is kept (24 fps) so the picture is exactly what the video
showed - no frames are dropped and none are blended (a blend of two frames is a
cross-dissolve, which reads as blur in motion).

    python frontend/scripts/build-scroll-frames.py                  (needs Pillow + ffmpeg)
    python frontend/scripts/build-scroll-frames.py --manifest-only  (re-hash the existing frames; no ffmpeg)

ffmpeg is taken from PATH, or from the `imageio-ffmpeg` pip package.
Output (committed): public/lets-scroll/frames/<scene>/NNN.webp (desktop),
public/lets-scroll/frames/<scene>-m/NNN.webp (phones, portrait crop), and
src/components/hero/frames.manifest.json (frame counts + a content `v`ersion for the engine).

`v` is a hash of every frame file. The engine appends it to each frame URL (`NNN.webp?v=...`) and
vite.config.ts puts it in index.html's poster preload, so the host can serve the frames with a
year-long immutable cache (vercel.json) and still hand out new frames the moment they change.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets-src" / "lets-scroll"   # source clips (not deployed)
PUBLIC = ROOT / "public" / "lets-scroll"
OUT = PUBLIC / "frames"
MANIFEST = ROOT / "src" / "components" / "hero" / "frames.manifest.json"

SCENES = ["reception", "booking", "care", "growth"]
FPS = 24  # the source frame rate: every frame is kept

# Desktop frames stay at the source's native 1280x720 - no resize, so nothing is softened here;
# the canvas does the single, high-quality scale to the screen. A light unsharp mask restores
# the bite the H.264 encode took off edges.
DESKTOP = {"size": (1280, 720), "quality": 74, "unsharp": ImageFilter.UnsharpMask(radius=0.9, percent=45, threshold=2)}
# Phones show a tall slice of a landscape video, so only the centre 9:16 column is ever visible
# - ship just that, at a size a phone can use.
MOBILE = {
    "size": (540, 960), "quality": 70, "crop_aspect": 9 / 16,
    "unsharp": ImageFilter.UnsharpMask(radius=1.1, percent=55, threshold=2),
}


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


def encode(job: tuple[str, str, dict]) -> None:
    """One frame: PNG -> (crop) -> (resize) -> sharpen -> WebP. Top-level so a process pool can run it."""
    src, dest, spec = job
    img = Image.open(src).convert("RGB")
    aspect = spec.get("crop_aspect")
    if aspect:
        w, h = img.size
        crop_w = round(h * aspect)
        left = (w - crop_w) // 2
        img = img.crop((left, 0, left + crop_w, h))
    if img.size != spec["size"]:
        img = img.resize(spec["size"], Image.LANCZOS)
    img.filter(spec["unsharp"]).save(dest, "WEBP", quality=spec["quality"], method=4)


def build(ffmpeg: str, clip: Path, out_dir: Path, spec: dict, pool: ProcessPoolExecutor) -> int:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as tmp:
        frames = extract(ffmpeg, clip, Path(tmp))
        jobs = [(str(f), str(out_dir / f"{i:03d}.webp"), spec) for i, f in enumerate(frames)]
        list(pool.map(encode, jobs, chunksize=8))
    return len(frames)


def frames_version() -> str:
    """Short content hash of every frame file (names + bytes), stable across machines."""
    h = hashlib.sha1()
    for scene in SCENES:
        for d in (OUT / scene, OUT / f"{scene}-m"):
            for f in sorted(d.glob("*.webp")):
                h.update(f"{d.name}/{f.name}".encode())
                h.update(f.read_bytes())
    return h.hexdigest()[:10]


def write_manifest(counts: dict[str, tuple[int, int]]) -> None:
    v = frames_version()
    manifest = {
        scene: {
            "desktop": {"dir": f"/lets-scroll/frames/{scene}", "count": count, "width": DESKTOP["size"][0], "height": DESKTOP["size"][1], "fps": FPS, "blend": False, "v": v},
            "mobile": {"dir": f"/lets-scroll/frames/{scene}-m", "count": count_m, "width": MOBILE["size"][0], "height": MOBILE["size"][1], "fps": FPS, "blend": False, "v": v},
        }
        for scene, (count, count_m) in counts.items()
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("wrote", MANIFEST.relative_to(ROOT), "- frames version", v)


def main() -> None:
    if "--manifest-only" in sys.argv:
        write_manifest({s: (len(list((OUT / s).glob("*.webp"))), len(list((OUT / f"{s}-m").glob("*.webp")))) for s in SCENES})
        return
    ffmpeg = find_ffmpeg()
    counts: dict[str, tuple[int, int]] = {}
    with ProcessPoolExecutor() as pool:
        for scene in SCENES:
            desktop_clip = SRC / f"{scene}.mp4"
            mobile_clip = SRC / f"{scene}-mobile.mp4"
            if not desktop_clip.exists():
                sys.exit(f"missing {desktop_clip}")
            count = build(ffmpeg, desktop_clip, OUT / scene, DESKTOP, pool)
            count_m = build(ffmpeg, mobile_clip if mobile_clip.exists() else desktop_clip, OUT / f"{scene}-m", MOBILE, pool)
            size = sum(f.stat().st_size for f in (OUT / scene).glob("*.webp"))
            size_m = sum(f.stat().st_size for f in (OUT / f"{scene}-m").glob("*.webp"))
            print(f"{scene:10} desktop {count} frames {size/1e6:5.1f} MB | mobile {count_m} frames {size_m/1e6:4.1f} MB", flush=True)
            counts[scene] = (count, count_m)
    write_manifest(counts)


if __name__ == "__main__":
    main()
