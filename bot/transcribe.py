"""Whole-episode transcript with word times, on a plain CPU (faster-whisper).

  python3 bot/transcribe.py episode.mp4 words.json [--model small|medium]   (default: medium under 25 min, else small)
  python3 bot/transcribe.py episode.mp4 part2.json --part 2/4     one quarter of the episode (GitHub: 4 machines at once)
  python3 bot/transcribe.py --merge words.json part0.json part1.json ...

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


def duration(src):
    try:
        return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src],
                                    capture_output=True, text=True).stdout.strip() or 0)
    except Exception:
        return 0.0


def speakers(words):
    """s0/s1 alternate on long gaps (pause marks only, never who is on camera)."""
    spk, last_end = 0, 0.0
    for w in words:
        if w["start"] - last_end > 1.2:
            spk ^= 1
        w["speaker"] = f"s{spk}"
        last_end = w["end"]
    return words


PAD = 4.0   # seconds of context each side of a part, so a word on the cut is heard whole; the overlap is dropped after


def main(src, out, model=None, part=None):
    """part = (i, n): transcribe the i-th n-th of the episode (times stay in episode seconds; the model is chosen
    from the whole episode's length, so four parts of a long podcast use "small" like the whole would)."""
    from faster_whisper import WhisperModel
    model = model or pick_model(src)
    wav = Path("/tmp/transcribe.wav")
    cut, a, b = [], 0.0, None
    if part:
        i, n = part
        dur = duration(src)
        a, b = i * dur / n, (i + 1) * dur / n
        a0, b0 = max(0.0, a - PAD), min(dur, b + PAD) if i < n - 1 else dur
        cut = ["-ss", f"{a0:.3f}", "-t", f"{b0 - a0:.3f}"]
        print(f"whisper {model} part {i + 1}/{n}: {a:.0f}-{b:.0f} s of {dur:.0f}")
    else:
        a0 = 0.0
        print(f"whisper {model}")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *cut, "-i", src, "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)
    m = WhisperModel(model, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(str(wav), word_timestamps=True, vad_filter=True, beam_size=1)
    words = []
    for s in segs:
        for w in s.words or []:
            st, en = round(w.start + a0, 2), round(w.end + a0, 2)
            if part and (st < a or (b is not None and part[0] < part[1] - 1 and st >= b)):
                continue   # the padding: another part owns these words
            words.append({"text": w.word.strip(), "start": st, "end": en, "speaker": "s0"})
    Path(out).write_text(json.dumps(speakers(words)))
    wav.unlink(missing_ok=True)
    print(f"{len(words)} words -> {out}")


def merge(out, parts):
    words = [w for p in parts for w in json.loads(Path(p).read_text())]
    words.sort(key=lambda w: (w["start"], w["end"]))
    Path(out).write_text(json.dumps(speakers(words)))
    print(f"{len(words)} words from {len(parts)} parts -> {out}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--merge" in a:
        merge(a[a.index("--merge") + 1], a[a.index("--merge") + 2:])
        sys.exit()
    model = a[a.index("--model") + 1] if "--model" in a else None
    part = tuple(int(x) for x in a[a.index("--part") + 1].split("/")) if "--part" in a else None
    main(a[0], a[1], model, part)
