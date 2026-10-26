"""ffmpeg helpers: probe, audio extraction, picture-change detection, clips and stills for Super VL."""

from __future__ import annotations

import asyncio
import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path

# Super VL accepts data URLs up to ~13.98M characters (~10 MiB before base64). Keep a safety margin.
MAX_CLIP_BYTES = int(9.0 * 1024 * 1024)


class MediaError(RuntimeError):
    pass


@dataclass(frozen=True)
class VideoInfo:
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool


async def _run(*args: str) -> tuple[str, str]:
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise MediaError(f"{args[0]} failed ({proc.returncode}): {err.decode(errors='replace')[-800:]}")
    return out.decode(errors="replace"), err.decode(errors="replace")


async def probe(path: Path) -> VideoInfo:
    out, _ = await _run(
        "ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)
    )
    data = json.loads(out)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if video is None:
        raise MediaError("no video stream found")
    num, _, den = (video.get("avg_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    duration = float(data.get("format", {}).get("duration") or video.get("duration") or 0)
    has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
    return VideoInfo(
        duration=duration,
        width=int(video["width"]),
        height=int(video["height"]),
        fps=fps,
        has_audio=has_audio,
    )


async def extract_audio(path: Path, wav: Path) -> Path:
    await _run(
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        str(path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(wav),
    )
    return wav


_PTS = re.compile(r"pts_time:([0-9.]+)")


async def detect_changes(path: Path, threshold: float = 0.3) -> list[float]:
    """Timestamps where the picture changes substantially (slide changes, cuts)."""
    _, err = await _run(
        "ffmpeg",
        "-v",
        "info",
        "-i",
        str(path),
        "-an",
        "-vf",
        f"scale=320:-2,select='gt(scene,{threshold})',showinfo",
        "-f",
        "null",
        "-",
    )
    return [
        float(m.group(1)) for line in err.splitlines() if "showinfo" in line for m in [_PTS.search(line)] if m
    ]


async def cut_clip(path: Path, start: float, end: float, out: Path, height: int = 480, fps: int = 2) -> Path:
    """Low-frame-rate, silent proxy clip for Super VL; shrinks until it fits the request size limit."""
    for h, crf in ((height, 30), (360, 34), (240, 38)):
        await _run(
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-ss",
            f"{start:.3f}",
            "-to",
            f"{end:.3f}",
            "-i",
            str(path),
            "-vf",
            f"fps={fps},scale=-2:{h}",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            str(crf),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out),
        )
        if out.stat().st_size <= MAX_CLIP_BYTES:
            return out
    raise MediaError(f"clip {start:.1f}-{end:.1f}s is still larger than {MAX_CLIP_BYTES} bytes")


async def still(path: Path, t: float, out: Path, max_width: int = 1280) -> Path:
    await _run(
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-ss",
        f"{max(t, 0):.3f}",
        "-i",
        str(path),
        "-frames:v",
        "1",
        "-vf",
        f"scale='min({max_width},iw)':-2",
        "-q:v",
        "3",
        str(out),
    )
    return out


def data_url(path: Path) -> str:
    mime = {".mp4": "video/mp4", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}[
        path.suffix.lower()
    ]
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
