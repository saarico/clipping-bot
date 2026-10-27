"""Whole-episode transcript with word times, on a plain CPU (faster-whisper).

  python3 bot/transcribe.py episode.mp4 words.json [--model small]

words.json = [{"text","start","end","speaker"}]. The speaker field only marks pauses between
sentences ("s0"/"s1" alternate on long gaps); who is on camera is decided by the face in the frame
(analyze_shots), never by a transcript label (RULES: speaker labels are not trusted).
"""
import json
import subprocess
import sys
from pathlib import Path


def main(src, out, model="small"):
    from faster_whisper import WhisperModel
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
    model = a[a.index("--model") + 1] if "--model" in a else "small"
    main(a[0], a[1], model)
