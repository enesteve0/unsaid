"""Captions for the demo video, made by Unsaid's own speech recognition (NVIDIA Parakeet, local and free).

cd video && uv run --project ../backend python captions.py      # writes build/captions.srt for YouTube
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "backend"))

from unsaid.asr import SpeechRecognizer  # noqa: E402
from unsaid.export import captions_srt  # noqa: E402

# Product names Parakeet spells the way it hears them ("Nematron", "Tavili").
NAMES = {"nematron": "Nemotron", "tavili": "Tavily", "nvidia": "NVIDIA", "token factory": "Token Factory"}


def main() -> None:
    video, wav = ROOT / "build" / "unsaid-demo.mp4", ROOT / "build" / "demo-audio.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(wav)],
        check=True,
    )
    words = SpeechRecognizer(ROOT.parent / "backend" / "models").transcribe_sync(wav).words
    srt = captions_srt(words)
    for heard, name in NAMES.items():
        srt = re.sub(rf"\b{heard}\b", name, srt, flags=re.IGNORECASE)
    (ROOT / "build" / "captions.srt").write_text(srt)
    print(f"build/captions.srt: {len(words)} words")


if __name__ == "__main__":
    main()
