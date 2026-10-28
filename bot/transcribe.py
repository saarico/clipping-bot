"""Whole-episode transcript with word times, on a plain CPU (faster-whisper).

  python3 bot/transcribe.py episode.mp4 words.json [--model small|medium]   (default: medium under 25 min, else small)

words.json = [{"text","start","end","speaker"}]. The speaker field only marks pauses between
sentences ("s0"/"s1" alternate on long gaps); who is on camera is decided by the face in the frame
(analyze_shots), never by a transcript label (RULES: speaker labels are not trusted).
"""
import json
import subprocess
import sys
from pathlib import Path


def pick_model(src):
    """"medium" for anything under 25 minutes (names and numbers come out right: "winter jacket", not
    "winner jacket"), "small" for long episodes so a 2-hour podcast still transcribes in time on a CPU."""
    try:
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src],
                                   capture_output=True, text=True).stdout.strip() or 0)
    except Exception:
        dur = 0
    return "medium" if 0 < dur < 25 * 60 else "small"


def main(src, out, model=None):
    from faster_whisper import WhisperModel
    model = model or pick_model(src)
    print(f"whisper {model}")
    wav = Path("/tmp/transcribe.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)
    m = WhisperModel(model, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(str(wav), word_timestamps=True, vad_filter=True, beam_size=1)
    words, spk, last_end = [], 0, 0.0
    for s in segs:
        for w in s.words or []:
            if w.start - last_end > 1.2:
                spk ^= 1
            words.append({"text": w.word.strip(), "start": round(w.start, 2), "end": round(w.end, 2), "speaker": f"s{spk}"})
            last_end = w.end
    Path(out).write_text(json.dumps(words))
    print(f"{len(words)} words -> {out}")


if __name__ == "__main__":
    a = sys.argv[1:]
    model = a[a.index("--model") + 1] if "--model" in a else None
    main(a[0], a[1], model)
