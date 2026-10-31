"""Sound Designer: the clip's audio, piece by piece.

In:  edits.json pieces + the spec (sfx, overlays, callouts) + the profile (talking show or not).
Out: audio.wav (levelled, 48 kHz, the contract file inspectors read) and audio.m4a (AAC for the Finisher).
Owns: join fades, loudness (two-pass linear loudnorm for talk, plain gain + limiter for movies/streams/music),
the optional whoosh under card reveals. Never touches the picture.
"""
import shutil

from render_clip import add_sfx, loudnorm_pass2, plain_gain, run


def mix(spec, src, pieces, overlays, whole_when_lost, tmp):
    """Writes tmp/audio.wav and tmp/audio.m4a. Returns {"pieces": n, "mode": "loudnorm" | "plain_gain", "sfx": bool}."""
    # audio: each piece with short fades so joins don't click; a softer fade at the very end
    ins, fc = [], []
    for i, (s, e, _) in enumerate(pieces):
        d = e - s
        tail = 0.25 if i == len(pieces) - 1 else 0.06
        ins += ["-ss", f"{s:.3f}", "-t", f"{d:.3f}", "-i", src]
        fc.append(f"[{i}:a]asetpts=PTS-STARTPTS,afade=in:d=0.04,afade=out:st={d - tail:.3f}:d={tail}[a{i}]")
    fc.append("".join(f"[a{i}]" for i in range(len(pieces))) + f"concat=n={len(pieces)}:v=0:a=1[cat]")
    run(["ffmpeg", "-loglevel", "error", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[cat]",
         "-ar", "48000", "-c:a", "pcm_s16le", str(tmp / "audio_raw.wav")])
    # loudnorm works at 192 kHz inside and the resample back can leave bunched or jumping packet
    # timestamps (rico heard Kylie's first 2 s sped up on YouTube, 2026-10-26). So: normalise into a
    # wav (no timestamps to get wrong), then encode that wav to AAC plainly.
    # podcasts: linear loudnorm. Movies/streams/concerts: a plain gain + limiter (rico, 2026-10-29: "the audio
    # sounds weird" on the trailer: loudnorm falls back to dynamic mode when the music's range beats LRA=11)
    af = loudnorm_pass2(tmp / "audio_raw.wav") if not whole_when_lost else plain_gain(tmp / "audio_raw.wav")
    run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(tmp / "audio_raw.wav"), "-af", af,
         "-ar", "48000", "-c:a", "pcm_s16le", str(tmp / "audio_norm.wav")])
    if spec.get("sfx"):
        add_sfx(tmp / "audio_norm.wav", pieces, overlays + list(spec.get("callouts", [])), tmp)
    run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(tmp / "audio_norm.wav"),
         "-c:a", "aac", "-b:a", "160k", str(tmp / "audio.m4a")])

    shutil.copyfile(tmp / "audio_norm.wav", tmp / "audio.wav")
    return {"pieces": len(pieces), "mode": "plain_gain" if whole_when_lost else "loudnorm", "sfx": bool(spec.get("sfx"))}
