"""Speech recognition with NVIDIA Parakeet TDT 0.6B v2 on CPU.

Runs the int8 ONNX export (`istupakov/parakeet-tdt-0.6b-v2-onnx`, model license CC-BY-4.0) through `onnx-asr`,
segmented by Silero VAD. Super VL has no audio input, so this is where Unsaid learns when people speak, what they
say, and where the silences are that can hold a description.
"""

from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import dataclass
from pathlib import Path

from .schemas import Interval, Word

MODEL_NAME = "nemo-parakeet-tdt-0.6b-v2"
TOKEN_STEP = 0.08  # Parakeet emits token start times on an 80 ms grid


@dataclass
class Transcript:
    words: list[Word]
    speech: list[Interval]  # VAD speech segments (more precise than word spans for "do not talk over")
    text: str


class SpeechRecognizer:
    """Lazily loads the models once per process and serialises inference (onnxruntime uses all cores itself)."""

    def __init__(self, models_dir: Path, threads: int | None = None) -> None:
        self.models_dir = models_dir
        self.threads = threads or int(os.getenv("ASR_THREADS", "4"))
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            import onnx_asr
            import onnxruntime as ort

            options = ort.SessionOptions()
            options.intra_op_num_threads = self.threads
            options.inter_op_num_threads = 1
            providers = ["CPUExecutionProvider"]
            vad = onnx_asr.load_vad(
                "silero", self.models_dir / "silero", sess_options=options, providers=providers
            )
            asr = onnx_asr.load_model(
                MODEL_NAME,
                self.models_dir / "parakeet-v2",
                quantization="int8",
                sess_options=options,
                providers=providers,
            )
            self._model = asr.with_vad(vad, min_silence_duration_ms=250, speech_pad_ms=30).with_timestamps()
        return self._model

    def warm_up(self) -> None:
        with self._lock:
            self._load()

    def transcribe_sync(self, wav: Path) -> Transcript:
        with self._lock:
            model = self._load()
            segments = list(model.recognize(str(wav)))
        return assemble(segments)

    async def transcribe(self, wav: Path) -> Transcript:
        return await asyncio.to_thread(self.transcribe_sync, wav)


def assemble(segments) -> Transcript:
    """Turn VAD segments of sub-word tokens into words with absolute start/end times."""
    words: list[Word] = []
    speech: list[Interval] = []
    texts: list[str] = []
    for seg in segments:
        speech.append(Interval(start=round(seg.start, 3), end=round(seg.end, 3)))
        texts.append((seg.text or "").strip())
        seg_words: list[list] = []  # [text, start]
        for i, (token, t) in enumerate(zip(seg.tokens or [], seg.timestamps or [], strict=False)):
            absolute = seg.start + t
            if i == 0 or token.startswith(" ") or not seg_words:
                seg_words.append([token.strip(), absolute])
            else:
                seg_words[-1][0] += token
        for j, (text, start) in enumerate(seg_words):
            if not text:
                continue
            nxt = seg_words[j + 1][1] if j + 1 < len(seg_words) else seg.end
            end = min(max(nxt, start + TOKEN_STEP), seg.end)
            words.append(Word(text=text, start=round(start, 3), end=round(end, 3)))
    return Transcript(words=words, speech=speech, text=" ".join(t for t in texts if t))
