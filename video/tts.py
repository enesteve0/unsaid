"""Voice the demo video with Kokoro-82M (Apache-2.0), then check every line by transcribing it back with Parakeet.

    cd video && uv run --project ../backend --with kokoro-onnx --with soundfile python tts.py

Numbers in the narration come from backend/eval/report.json and the sample's result.json, never typed by hand.
"""

from __future__ import annotations

import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

import soundfile as sf
from kokoro_onnx import Kokoro

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
BUILD = ROOT / "build" / "tts"
sys.path.insert(0, str(REPO / "backend"))


def money_words(usd: float) -> str:
    cents = usd * 100
    if cents < 1:
        return "less than one cent"
    if cents < 10:
        n = round(cents)
        return f"about {['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine'][n]} cent{'s' if n != 1 else ''}"
    return f"about {round(cents)} cents"


def percent_words(x: float) -> str:
    return f"{round(x * 100)} percent"


def fill(text: str, report: dict, sample: dict) -> str:
    values: dict[str, str] = {}
    if report.get("available"):
        sys_ = {s["key"]: s["metrics"] for s in report["systems"]}
        u, o = sys_["unsaid"], sys_["oneshot"]
        values["evaluation_sentence"] = (
            f"On {report['clips']} lectures, Unsaid spoke over the lecturer for {u['talk_over']:.1f} seconds a minute, "
            f"against {o['talk_over']:.1f} for the one-shot approach, and covered {percent_words(u['coverage'])} of the "
            f"pointing moments, against {percent_words(o['coverage'])}."
        )
        values["usd_per_min_words"] = money_words(u["usd_per_min"])
    else:
        values["evaluation_sentence"] = ""
        minutes = sample["video"]["duration"] / 60
        values["usd_per_min_words"] = money_words(sample["ledger"]["summary"]["total_usd"] / minutes)
    return re.sub(r"\{\{(\w+)\}\}", lambda m: values.get(m.group(1), ""), text).replace("  ", " ")


def hero_cue(sample: dict, start: float, end: float) -> dict:
    cues = [c for c in sample["cues"] if c["tier"] != "never" and start <= c["start"] <= end + 6]
    if not cues:
        raise SystemExit("no description inside the cold-open window; adjust cold_open in scenes.json")
    return cues[0]


def main() -> None:
    script = json.loads((ROOT / "scenes.json").read_text())
    report_path = REPO / "backend" / "eval" / "report.json"
    report = json.loads(report_path.read_text()) if report_path.exists() else {"available": False}
    sample = json.loads((REPO / "samples" / script["sample"] / "result.json").read_text())
    BUILD.mkdir(parents=True, exist_ok=True)
    kokoro = Kokoro(str(ROOT / "models" / "kokoro-v1.0.onnx"), str(ROOT / "models" / "voices-v1.0.bin"))

    lines: dict[str, dict] = {}
    for scene in script["scenes"]:
        text = fill(scene["narration"], report, sample)
        audio, rate = kokoro.create(text, voice=script["narrator_voice"], speed=1.0, lang="en-us")
        path = BUILD / f"{scene['id']}.wav"
        sf.write(path, audio, rate)
        lines[scene["id"]] = {"text": text, "seconds": round(len(audio) / rate, 3), "path": str(path)}

    co = script["cold_open"]
    cue = hero_cue(sample, co["lecture_start"], co["lecture_end"])
    audio, rate = kokoro.create(cue["text"], voice=script["describer_voice"], speed=1.0, lang="en-us")
    path = BUILD / "describer.wav"
    sf.write(path, audio, rate)
    lines["describer"] = {"text": cue["text"], "seconds": round(len(audio) / rate, 3), "path": str(path), "cue_start": cue["start"]}

    # Round trip: does speech recognition hear what we meant? Catches mispronounced names before the edit.
    from unsaid.asr import SpeechRecognizer

    asr = SpeechRecognizer(REPO / "backend" / "models")
    for key, line in lines.items():
        heard = asr.transcribe_sync(Path(line["path"])).text
        norm = lambda s: re.sub(r"[^a-z0-9 ]", "", s.lower())  # noqa: E731
        line["heard"] = heard
        line["match"] = round(SequenceMatcher(None, norm(line["text"]), norm(heard)).ratio(), 3)
        flag = "" if line["match"] > 0.9 else "   <-- check pronunciation"
        print(f"{key:11} {line['seconds']:5.1f}s match {line['match']:.2f}{flag}\n   heard: {heard}")
    (BUILD / "lines.json").write_text(json.dumps(lines, indent=1))
    print("total narration", round(sum(v["seconds"] for k, v in lines.items() if k != "describer"), 1), "s")


if __name__ == "__main__":
    main()
