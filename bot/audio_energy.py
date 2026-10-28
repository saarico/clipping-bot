"""Loudness per second of an episode (RMS dB), so moment picking can hear where a stream or a
performance gets loud (crowd, chorus, a scream) instead of reading words only.

  python3 bot/audio_energy.py episode.mp4 energy.json     -> [dB per second]
"""
import json
import re
import subprocess
import sys


def energy(src):
    r = subprocess.run(["ffmpeg", "-loglevel", "info", "-i", str(src), "-vn", "-af",
                        "aformat=channel_layouts=mono,aresample=16000,asetnsamples=16000,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
                        "-f", "null", "-"], capture_output=True, text=True)
    # silence prints -inf; keep it as a very quiet second so the index stays the second of the episode
    vals = re.findall(r"lavfi\.astats\.Overall\.RMS_level=(-?[\d.]+|-inf)", r.stdout)
    return [max(float(v), -70.0) if v != "-inf" else -70.0 for v in vals]


def window(e, start, end):
    """(mean dB over the window minus the episode median, number of loud seconds) or None."""
    if not e:
        return None
    seg = e[int(start):max(int(end), int(start) + 1)]
    if not seg:
        return None
    med = sorted(e)[len(e) // 2]
    loud = sum(1 for v in seg if v > med + 6)
    return sum(seg) / len(seg) - med, loud


if __name__ == "__main__":
    out = energy(sys.argv[1])
    json.dump(out, open(sys.argv[2], "w"))
    print(f"{len(out)} seconds -> {sys.argv[2]}")
