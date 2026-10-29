"""Assemble the demo video from the recordings, the narration and the lecture audio.

    cd video && uv run --project ../backend python assemble.py

Order: cold open as heard → "Which points?" → cold open with Unsaid → title → narrated app scenes → end card.
Every segment is encoded identically (1920x1080, 30 fps, H.264, AAC 48 kHz stereo) and joined without re-encoding.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
BUILD = ROOT / "build"
SEG = BUILD / "segments"
FONTS = ROOT / "fonts"
W, H, FPS = 1920, 1080, 30
INK, PAPER, DIM, AMBER = "0x0d0c0a", "0xefe8da", "0xc2b9a8", "0xffb340"
ENCODE = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
          "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart"]


def run(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def duration(path: Path) -> float:
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return float(out)


def card(out: Path, seconds: float, lines: list[tuple[str, str, int, str, int]]) -> None:
    """A still card rendered with Pillow in the app's typefaces. lines: (text, font file, size, colour, y offset)."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (W, H), "#" + INK[2:])
    draw = ImageDraw.Draw(image)
    for t, font, size, colour, dy in lines:
        face = ImageFont.truetype(str(FONTS / font), size)
        left, top, right, bottom = draw.textbbox((0, 0), t, font=face)
        draw.text(((W - (right - left)) / 2 - left, (H - (bottom - top)) / 2 - top + dy), t, font=face, fill="#" + colour[2:])
    png = out.with_suffix(".png")
    image.save(png)
    fade_out = max(seconds - 0.4, 0)
    run(
        "-loop", "1", "-t", str(seconds), "-i", str(png),
        "-f", "lavfi", "-t", str(seconds), "-i", "anullsrc=r=48000:cl=stereo",
        "-vf", f"fps={FPS},fade=in:st=0:d=0.4,fade=out:st={fade_out}:d=0.4",
        *ENCODE, "-shortest", str(out),
    )


def scene(rec: Path, narration: Path, out: Path, speedup: bool) -> None:
    """Fit a silent recording to its narration: speed it up, trim it, or hold its last frame."""
    target = duration(narration) + 0.9
    length = duration(rec)
    if speedup and length > target:
        video = f"setpts=PTS*{target / length:.5f}"
    elif length >= target:
        video = "null"
    else:
        video = f"tpad=stop_mode=clone:stop_duration={target - length + 0.1:.2f}"
    run(
        "-i", str(rec), "-i", str(narration),
        "-filter_complex",
        f"[0:v]{video},scale={W}:{H},fps={FPS},trim=0:{target:.2f},setpts=PTS-STARTPTS,"
        f"fade=in:st=0:d=0.3,fade=out:st={target - 0.35:.2f}:d=0.35[v];"
        f"[1:a]adelay=300|300,apad,atrim=0:{target:.2f},aresample=48000[a]",
        "-map", "[v]", "-map", "[a]", *ENCODE, str(out),
    )


def cold(rec: Path, play_at: float, lecture: Path, seconds: float, out: Path, describer: Path | None = None, cue_offset: float = 0.0, tail: float = 1.2, hold: float = 0.0) -> None:
    """The full-screen player recording, with the lecture audio (and the description voice) laid back on.

    `hold`: a paused (extended) description stopped the picture for this long at cue_offset, so the lecture audio
    stops there too, and the description is heard in that silence, never over the lecturer.
    """
    total = play_at + seconds + hold + tail
    inputs = ["-i", str(rec), "-i", str(lecture)]
    delay = int(play_at * 1000)
    if hold:
        audio = (
            f"[1:a]atrim=0:{cue_offset:.3f},asetpts=PTS-STARTPTS[l1];"
            f"[1:a]atrim={cue_offset:.3f},asetpts=PTS-STARTPTS[l2];"
            f"anullsrc=r=48000:cl=stereo,atrim=0:{hold:.3f}[gap];"
            f"[l1][gap][l2]concat=n=3:v=0:a=1,adelay={delay}|{delay},apad[lec]"
        )
    else:
        audio = f"[1:a]adelay={delay}|{delay},apad[lec]"
    mix = "[lec]"
    if describer is not None:
        inputs += ["-i", str(describer)]
        d = int((play_at + cue_offset) * 1000)
        audio += f";[2:a]adelay={d}|{d},volume=1.15,apad[ad];[lec][ad]amix=inputs=2:duration=longest:normalize=0[mix]"
        mix = "[mix]"
    run(
        *inputs,
        "-filter_complex",
        f"[0:v]tpad=stop_mode=clone:stop_duration=6,trim=0:{total:.2f},setpts=PTS-STARTPTS,scale={W}:{H},fps={FPS},"
        f"fade=in:st=0:d=0.5,fade=out:st={total - 0.4:.2f}:d=0.4[v];{audio};{mix}atrim=0:{total:.2f},aresample=48000[a]",
        "-map", "[v]", "-map", "[a]", *ENCODE, str(out),
    )


def main() -> None:
    script = json.loads((ROOT / "scenes.json").read_text())
    lines = json.loads((BUILD / "tts" / "lines.json").read_text())
    timing = json.loads((BUILD / "rec" / "timing.json").read_text())
    SEG.mkdir(parents=True, exist_ok=True)
    co = script["cold_open"]
    seconds = co["lecture_end"] - co["lecture_start"]

    source = REPO / "samples" / script["sample"] / "video.mp4"
    lecture = BUILD / "lecture.wav"
    run("-ss", str(co["lecture_start"]), "-t", f"{seconds:.2f}", "-i", str(source), "-vn", "-ac", "2", "-ar", "48000", str(lecture))

    parts: list[Path] = []
    cold(BUILD / "rec" / "cold_heard.webm", timing["cold_heard"], lecture, seconds, SEG / "01_heard.mp4")
    parts.append(SEG / "01_heard.mp4")
    card(SEG / "02_question.mp4", 2.4, [(co["question"], "InstrumentSerif-Italic.ttf", 120, PAPER, 0)])
    parts.append(SEG / "02_question.mp4")
    cue_offset = lines["describer"]["cue_start"] - co["lecture_start"]
    hold = lines["describer"]["seconds"] + 0.4 if lines["describer"].get("extended") else 0.0
    tail = 1.2 if hold else max(1.2, lines["describer"]["seconds"] + cue_offset - seconds + 0.8)
    cold(BUILD / "rec" / "cold_unsaid.webm", timing["cold_unsaid"], lecture, seconds, SEG / "03_unsaid.mp4",
         describer=Path(lines["describer"]["path"]), cue_offset=cue_offset, tail=tail, hold=hold)
    parts.append(SEG / "03_unsaid.mp4")
    card(SEG / "04_title.mp4", 3.2, [
        ("Unsaid", "InstrumentSerif-Regular.ttf", 190, PAPER, -40),
        ("Audio description for everything a lecture shows but never says.", "AtkinsonHyperlegibleNext.ttf", 40, DIM, 110),
    ])
    parts.append(SEG / "04_title.mp4")

    for i, s in enumerate(script["scenes"], start=5):
        out = SEG / f"{i:02d}_{s['id']}.mp4"
        scene(BUILD / "rec" / f"{s['id']}.webm", Path(lines[s["id"]]["path"]), out, s.get("speedup_to_narration", False))
        parts.append(out)

    end = script["end_card"]
    card(SEG / "99_end.mp4", end["seconds"], [
        (end["title"], "InstrumentSerif-Regular.ttf", 170, PAPER, -90),
        (end["lines"][0], "AtkinsonHyperlegibleNext.ttf", 40, DIM, 60),
        (end["lines"][1], "AtkinsonHyperlegibleNext.ttf", 40, AMBER, 125),
        *[(line, "IBMPlexMono-Regular.ttf", 30, DIM, 200 + 50 * n) for n, line in enumerate(end.get("links", []))],
    ])
    parts.append(SEG / "99_end.mp4")

    listing = BUILD / "parts.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in parts))
    final = BUILD / "unsaid-demo.mp4"
    run("-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(final))
    print(f"{final}  {duration(final):.1f} s")


if __name__ == "__main__":
    main()
