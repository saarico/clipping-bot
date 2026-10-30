"""One pass over Drive. Runs every 5 hours on GitHub (workflow run.yml) or by hand:

  python3 bot/run.py [campaign folder name]

For every folder under CLIPPING/:
  0_START   requirements file -> brief.json; episode.mp4 (or a YouTube link in the brief) -> transcript
  1_CHECK   <- up to 3 clips + SUMMARY doc, once the transcript and the plan exist
  2_REDO    rico's critique docs -> saved to campaigns/<c>/critiques/ for the reviewer; clips re-picked
  3_APPROVED  each clip gets its POST KIT entry (title, description, tags, rules to re-check)
State lives in campaigns/<c>/state.json (committed by the workflow). Videos never enter git.
Drive access: rclone (bot/drive.py); tests: CLIPPING_LOCAL=/some/dir uses a plain folder as the Drive.
"""
import json
import re
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import brief as briefer  # noqa: E402
import drive  # noqa: E402
import pipeline  # noqa: E402
import post_kit  # noqa: E402
import lanes  # noqa: E402

WORK = Path(os.environ.get("CLIP_WORK", "/tmp/clipwork"))
PREP = WORK / "prep"    # what the render machines need (specs, transcript, graphics map): a GitHub artifact
OUT = WORK / "out"      # what each render machine sends back (clip folder + result.json)
MATRIX_MAX = 4          # candidates rendered at once on separate machines (3 clips wanted; one spare)
REQ_EXT = (".pdf", ".docx", ".doc", ".txt", ".md")
VID_EXT = (".mp4", ".mov", ".mkv", ".webm", ".m4v")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def log(*a):
    print(f"[{datetime.now(timezone.utc):%H:%M:%S}]", *a, flush=True)


def state_path(name):
    return ROOT / "campaigns" / name / "state.json"


def load_state(name):
    p = state_path(name)
    return json.loads(p.read_text()) if p.exists() else {"name": name, "log": []}


def save_state(name, st):
    p = state_path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    st["updated"] = now()
    p.write_text(json.dumps(st, indent=1))


def note(st, msg):
    log(msg)
    st["log"] = (st.get("log", []) + [f"{now()}  {msg}"])[-40:]


BOT_DOCS = {"BRIEF", "NEEDS THE VIDEO", "SUMMARY", "POST KIT", "JOIN", "RULES (fetched by the bot)"}


def is_bot_doc(f):
    return f["Name"].rsplit(".", 1)[0] in BOT_DOCS


def get_footage(name, st, stage):
    """Brand mode: every video in 0_START, kept as separate files (app demos, b-roll)."""
    fdir = WORK / name / "footage"
    fdir.mkdir(parents=True, exist_ok=True)
    vids = sorted(drive.files(stage["0_START"], VID_EXT), key=lambda f: f["Name"])
    for v in vids:
        local = fdir / re.sub(r"^Copy of ", "", v["Name"])
        if not local.exists():
            drive.download(v["Path"], local)
    return fdir if any(fdir.iterdir()) else None


def has_speech(path):
    """False for silent product footage (no audio stream, or audio under -45 dB on average)."""
    r = subprocess.run(["ffmpeg", "-i", str(path), "-t", "600", "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"mean_volume: (-?[\d.]+)", r.stderr)
    return bool(m) and float(m.group(1)) > -45


def yt_cookies():
    """yt-dlp flags for the YT_COOKIES secret (Netscape cookies.txt of a THROWAWAY Google account, never rico's own):
    YouTube refuses every GitHub machine without a signed-in session ("Sign in to confirm you're not a bot")."""
    raw = os.environ.get("YT_COOKIES", "").strip()
    if not raw:
        return []
    p = Path("/tmp/yt_cookies.txt")
    if not p.exists():
        p.write_text(raw + "\n")
        p.chmod(0o600)
    return ["--cookies", str(p)]


def fetch_link(url, dest, st):
    """One source link -> episode.mp4. Google Drive files and folders (shared with anyone) via gdown,
    Dropbox and direct video links via curl, everything else via yt-dlp (YouTube blocks GitHub runners)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / "dl"
    tmp.mkdir(exist_ok=True)
    if re.search(r"drive\.google\.com|docs\.google\.com/.*(file|folder)", url):
        note(st, f"downloading from Google Drive: {url[:80]}")
        folder = "/folders/" in url
        subprocess.run(["gdown", "--fuzzy", "--quiet", "-O", str(tmp) + "/"] + (["--folder"] if folder else []) + [url], check=False, timeout=7200)
    elif re.search(r"dropbox\.com|\.(mp4|mov|mkv|webm|m4v)(\?|$)", url):
        note(st, f"downloading file: {url[:80]}")
        u = re.sub(r"[?&]dl=0", "", url)
        u += ("&" if "?" in u else "?") + "dl=1" if "dropbox.com" in u else ""
        subprocess.run(["curl", "-sL", "--max-time", "7000", "-o", str(tmp / "episode_dl.mp4"), u], check=False, timeout=7200)
    else:
        ck = yt_cookies()
        note(st, f"trying yt-dlp{' with cookies' if ck else ' (no YT_COOKIES secret: YouTube will refuse)'}: {url[:80]}")
        r = subprocess.run(["yt-dlp", "-f", "bv*[height<=1080]+ba/b[height<=1080]/b", "-S", "res:1080,vcodec:h264,ext:mp4:m4a", "--merge-output-format", "mp4",   # h264 first: ffmpeg decodes it fastest
                            "--js-runtimes", "node", "--no-playlist", "--socket-timeout", "30", "-N", "4", "--retries", "5", *ck, "-o", str(tmp / "episode_dl.%(ext)s"), url],
                           capture_output=True, text=True, timeout=3600)
        err = (r.stderr or "")[-400:]
        if "Sign in to confirm" in err or "not a bot" in err or "cookies" in err.lower() and "invalid" in err.lower():
            note(st, "YOUTUBE COOKIES NEEDED OR EXPIRED: refresh the YT_COOKIES secret (SETUP.md, YouTube section)")
        elif r.returncode != 0:
            note(st, f"yt-dlp failed: {err.strip().splitlines()[-1][:160] if err.strip() else r.returncode}")
    vids = sorted((p for p in tmp.rglob("*") if p.suffix.lower() in VID_EXT and p.stat().st_size > 1e6), key=lambda p: -p.stat().st_size)
    if not vids:
        return None
    if len(vids) == 1:
        vids[0].replace(dest)
        return dest
    return join_videos(vids, dest)   # several files: one episode in name order


def video_info(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
                        "-of", "json", str(path)], capture_output=True, text=True)
    try:
        j = json.loads(r.stdout)
        st0 = (j.get("streams") or [{}])[0]
        return int(st0.get("width", 0)), int(st0.get("height", 0)), float(j["format"]["duration"])
    except Exception:
        return 0, 0, 0.0


def bars_crop(path, dur):
    """ffmpeg cropdetect on a few seconds in the middle: 'crop=w:h:x:y' of the picture without black bars."""
    r = subprocess.run(["ffmpeg", "-ss", f"{max(dur / 2 - 4, 0):.1f}", "-t", "8", "-i", str(path), "-vf", "cropdetect=24:16:0",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = re.findall(r"crop=\d+:\d+:\d+:\d+", r.stderr)
    return m[-1] if m else None


def join_videos(parts, dest, log=print):
    """Several source files -> one 1920x1080 30 fps episode. Duplicate downloads (same size) are dropped,
    vertical files are left out (they are finished social cuts, not raw material), black bars are cut
    away and wide pictures are centre-cropped to 16:9 so no clip ever shows a letterbox."""
    norm, seen = [], set()
    for i, pth in enumerate(sorted(parts, key=lambda p: p.name)):
        size = pth.stat().st_size
        if size in seen:
            log(f"skipped duplicate {pth.name}")
            continue
        seen.add(size)
        w, h, dur = video_info(pth)
        if h > w:
            log(f"skipped vertical file {pth.name} ({w}x{h})")
            continue
        crop = bars_crop(pth, dur)
        vf = ((crop + ",") if crop else "") + "scale=-2:1080:flags=bicubic,crop='min(iw,1920)':1080,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1"
        o = dest.parent / "parts" / f"n{i:02d}.mp4"
        o.parent.mkdir(parents=True, exist_ok=True)
        # veryfast crf 21: about 4 Mbit/s. ultrafast crf 17 wrote ~20 Mbit/s, 10 GB for a 1-hour 4K episode, and the
        # GitHub machine ran out of disk (Higgsfield, 2026-10-30)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(pth), "-vf", vf, "-r", "30", "-c:v", "libx264", "-preset", "veryfast",
                        "-crf", "21", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-af", "aresample=async=1", str(o)], check=False)
        ow, oh, odur = video_info(o) if o.exists() else (0, 0, 0.0)
        if (ow, oh) != (1920, 1080) or abs(odur - dur) > max(2.0, 0.02 * dur):
            # a conversion that stopped short (disk full, killed) must never become the episode: run 1 of Higgsfield
            # cached a 5 GB torso with no sound (2026-10-30)
            log(f"part {i:02d}: conversion of {pth.name[:60]} came out {ow}x{oh} {odur:.0f}s of {dur:.0f}s: dropped")
            o.unlink(missing_ok=True)
            continue
        norm.append(o)
        log(f"part {i:02d}: {pth.name[:60]} {w}x{h} {dur:.0f}s" + (f" ({crop})" if crop else ""))
        pth.unlink(missing_ok=True)   # the original is not needed again on this machine
    if not norm:
        return None
    lst = dest.parent / "parts" / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in norm))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(dest)], check=False)
    if dest.exists():
        for p in norm:
            p.unlink(missing_ok=True)
    return dest if dest.exists() else None


THUMB_VERSION = "v2"   # bump when thumbnail.py changes its look: approved clips get their thumbnail remade


def plan_thumb(cdir, c):
    """The reviewer's thumbnail pins (thumb_text, thumb_t, emphasis) for a kept clip: the plan.json clip whose
    parts overlap the clip's parts."""
    try:
        plan = json.loads((cdir / "plan.json").read_text())
    except Exception:
        return {}
    mine = c.get("parts") or []
    for pc in plan.get("clips", []):
        for a, b in pc.get("parts", []):
            if any(min(b, q) - max(a, p) > 0.5 * min(b - a, q - p) for p, q in mine):
                return {"thumb_text": pc.get("thumb_text", ""), "thumb_t": pc.get("thumb_t"), "emphasis": pc.get("emphasis", [])}
    return {}


def thumb_sig(cdir, c):
    """What the approved clip's thumbnail was made from: look version + the reviewer's pins."""
    pins = plan_thumb(cdir, c)
    return f"{THUMB_VERSION}|{pins.get('thumb_text', '')}|{pins.get('thumb_t')}"


def ensure_thumbnail(name, st, stage, cdir, f, c):
    """An approved clip's thumbnail: built from the episode's own frames, uploaded beside the clip (PNG + the
    options sheet), and the clip re-uploaded with the thumbnail as its last two frames. Remade when the reviewer's
    pins (thumb_text / thumb_t in plan.json) or the thumbnail look (THUMB_VERSION) changed since the last one.
    Returns the PNG's name in 3_APPROVED, or "" when the source is not available."""
    import thumbnail
    stem = Path(f["Name"]).stem
    png_name, opts_name = f"{stem}_thumbnail.png", f"{stem}_thumbnail_options.jpg"
    pins = plan_thumb(cdir, c)
    sig = thumb_sig(cdir, c)
    have = {x["Name"] for x in drive.files(stage["3_APPROVED"], {".png", ".jpg"})}
    if png_name in have and c.get("thumb_sig") == sig:
        return png_name
    if not c.get("parts"):
        return ""
    try:
        src = get_source(name, st, stage, cdir)
        if not src:
            return ""
        work = WORK / name / "thumbs"
        work.mkdir(parents=True, exist_ok=True)
        png, opts = work / png_name, work / opts_name
        thumbnail.make(str(src), c.get("hook", ""), c["parts"], str(png), text=pins.get("thumb_text"), at=pins.get("thumb_t"),
                       emphasis=pins.get("emphasis", []), options=str(opts))
        local = work / f["Name"]
        drive.download(f["Path"], str(local))
        # every clip rendered since 2026-10-29 03:10 UTC already ends with a cover frame (pipeline.one_clip appends one
        # before the clip reaches 1_CHECK): always cut it off, or a remade thumbnail stacked a second still on the first
        thumbnail.append_cover(local, png, strip_old=True)
        drive.upload(str(png), stage["3_APPROVED"], name=png_name)
        if opts.exists():
            drive.upload(str(opts), stage["3_APPROVED"], name=opts_name)
        drive.upload(str(local), stage["3_APPROVED"], name=f["Name"])     # same name: the clip with the cover frame at the end
        c["thumb_sig"] = sig
        note(st, f"thumbnail made for {f['Name']} (PNG + options sheet + last-frame cover"
                 f"{', pinned at ' + str(pins['thumb_t']) + ' s' if pins.get('thumb_t') is not None else ''})")
        return png_name
    except Exception as e:
        log(f"thumbnail for {f['Name']} failed: {e}")
        return ""


YT_ID = re.compile(r"\[([A-Za-z0-9_-]{11})\]")   # yt-dlp names downloads "Title [videoid].mp4"


def get_source(name, st, stage, cdir, for_audio=False):
    """Episode file: from 0_START, else yt-dlp on the brief's first link (best effort).
    for_audio (the transcribe machines): the single raw file as it is, no conversion, no cache writes; several
    files = None (their joined timeline exists only after prepare converts them)."""
    dest = WORK / name / "episode.mp4"
    if dest.exists():
        return dest
    vids = sorted(drive.files(stage["0_START"], VID_EXT), key=lambda f: f["Name"])
    if vids:
        import hashlib
        sig = hashlib.md5("|".join(f"{v['Name']}:{v.get('Size')}" for v in vids).encode()).hexdigest()[:12]
        cache = f"{drive.root()}/_cache/{name}"   # a converted episode is kept on Drive, so a redo skips download + convert
        cached = {f["Name"]: f for f in drive.files(cache)}
        if "episode.mp4" in cached and "source.json" in cached:
            try:
                meta = json.loads(drive.text_of(cached["source.json"]["Path"], "source.json"))
                if meta.get("sig") == sig and (not meta.get("size") or int(meta["size"]) == int(cached["episode.mp4"].get("Size") or -1)):
                    note(st, "episode taken from the Drive cache (same source files as last time)")
                    return drive.download(cached["episode.mp4"]["Path"], dest)
                if meta.get("sig") == sig:
                    note(st, "the Drive cache holds a cut-short episode (size mismatch): rebuilding it")
            except Exception as e:
                note(st, f"cache check failed ({type(e).__name__}); rebuilding the episode")
        got = None
        if len(vids) == 1:
            # one file: used as is when it already is 1920x1080 landscape, else converted like a joined episode
            # (render_clip refuses any other size; a 1280x720 or 4K episode stopped every render with SystemExit)
            m = YT_ID.search(vids[0]["Name"])   # rico's own yt-dlp download: "Title [videoid].mp4"
            yt = next((u for u in st.get("brief", {}).get("links", []) if m and m.group(1) in u and re.search(r"youtu\.?be", u)), None)
            if yt and os.environ.get("YT_COOKIES") and not for_audio:
                # the same video is in the brief's YouTube link: its 1080p h264 copy downloads in minutes, while a 4K file
                # from Drive took the better part of an hour to convert (Higgsfield, 2026-10-30)
                note(st, f"{vids[0]['Name'][:60]} is the brief's YouTube video: taking the 1080p copy from YouTube")
                try:
                    got = fetch_link(yt, dest, st)
                except Exception as e:
                    note(st, f"YouTube copy failed ({type(e).__name__}: {str(e)[:80]}); using the file from 0_START")
            if not got:
                note(st, f"downloading {vids[0]['Name']} from 0_START")
                one = drive.download(vids[0]["Path"], dest.parent / "parts" / f"00_{vids[0]['Name']}")
                w, h, _ = video_info(one)
                if (w, h) == (1920, 1080):
                    shutil.move(str(one), str(dest))
                    return dest
                if for_audio:
                    return one
                note(st, f"{vids[0]['Name'][:60]} is {w}x{h}: converting to 1920x1080 30 fps")
                parts = [one]
        elif for_audio:
            return None
        else:   # several files (scene clips, trailers, episode parts): one landscape episode in name order
            todo, sizes = [], set()
            for v in vids:   # don't even download duplicates or finished vertical cuts
                if v.get("Size") in sizes:
                    note(st, f"skipped duplicate {v['Name'][:60]}")
                elif re.search(r"vertical|igtv|9x16|9_16|portrait|reels|tiktok|shorts", v["Name"], re.I):
                    note(st, f"skipped vertical cut {v['Name'][:60]}")
                else:
                    todo.append(v)
                sizes.add(v.get("Size"))
            note(st, f"downloading {len(todo)} of {len(vids)} videos from 0_START and joining them")
            parts = [drive.download(v["Path"], dest.parent / "parts" / f"{i:02d}_{v['Name']}") for i, v in enumerate(todo)]
        out = got or join_videos(parts, dest, log=lambda m: note(st, m))
        if not out:
            note(st, "the video in 0_START could not be converted (no usable landscape picture)")
        if out:
            try:
                meta = dest.parent / "source.json"
                meta.write_text(json.dumps({"sig": sig, "files": [v["Name"] for v in vids], "size": Path(out).stat().st_size}))
                drive.be().mkdir(cache)
                drive.upload(out, cache, name="episode.mp4")
                up = {f["Name"]: f for f in drive.files(cache)}.get("episode.mp4", {})
                if int(up.get("Size") or -1) != Path(out).stat().st_size:
                    raise RuntimeError(f"upload came out {up.get('Size')} bytes of {Path(out).stat().st_size}")
                drive.upload(meta, cache, name="source.json")
                note(st, "episode saved to the Drive cache")
            except Exception as e:
                note(st, f"cache save skipped ({type(e).__name__}: {str(e)[:80]})")
            return out
    links = st.get("brief", {}).get("links", [])
    if links and not st.get("download_failed"):
        if for_audio and len(links) > 1:   # whichever link works, prepare caches it; a transcribe machine tries the first only
            links = links[:1]
        import hashlib
        sig = "links:" + hashlib.md5("|".join(links[:6]).encode()).hexdigest()[:12]
        cache = f"{drive.root()}/_cache/{name}"   # a downloaded episode is kept on Drive: YouTube is asked once, not on every machine
        cached = {f["Name"]: f for f in drive.files(cache)}
        if "episode.mp4" in cached and "source.json" in cached:
            try:
                meta = json.loads(drive.text_of(cached["source.json"]["Path"], "source.json"))
                if meta.get("sig") == sig and (not meta.get("size") or int(meta["size"]) == int(cached["episode.mp4"].get("Size") or -1)):
                    note(st, "episode taken from the Drive cache (downloaded from the link last time)")
                    return drive.download(cached["episode.mp4"]["Path"], dest)
            except Exception as e:
                note(st, f"cache check failed ({type(e).__name__}); downloading again")
        errors = []
        for url in links[:6]:
            try:
                got = fetch_link(url, dest, st)
            except Exception as e:
                got = None
                errors.append(f"{url[:60]}: {type(e).__name__} {str(e)[:80]}")
            if got:
                if for_audio:
                    return got
                try:
                    meta = dest.parent / "source.json"
                    meta.write_text(json.dumps({"sig": sig, "url": url, "size": Path(got).stat().st_size}))
                    drive.be().mkdir(cache)
                    drive.upload(got, cache, name="episode.mp4")
                    drive.upload(meta, cache, name="source.json")
                    note(st, "episode saved to the Drive cache")
                except Exception as e:
                    note(st, f"cache save skipped ({type(e).__name__}: {str(e)[:80]})")
                return got
        st["download_failed"] = True
        note(st, "no link could be downloaded; asked rico for the file")
        drive.write_doc("NEEDS THE VIDEO", "The bot could not download the episode from the links in the requirements.\n\n"
                        "YouTube link: the YouTube cookies in the GitHub secret YT_COOKIES are missing or expired (SETUP.md, 'YouTube episodes from the cloud').\n"
                        "Drive / Dropbox link: it must be shared with anyone who has the link.\n"
                        "Or put the episode file in this folder (any name, mp4/mov/mkv). "
                        "The bot picks it up on its next run (every 5 hours).\n\nTried:\n- " + "\n- ".join(errors or links[:6]), stage["0_START"])
    return None


IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
TRANSCRIBE_PARTS = 4    # transcribe machines per run (run.yml matrix); a 1-hour podcast takes a quarter each
WORDS = WORK / "words"  # what a transcribe machine sends back: <campaign>/part_<i>.json (artifact words-<i>)


def transcribe_job(i, n, only=None):
    """One of n machines: for every campaign that has an episode but no transcript yet, transcribe the i-th n-th.
    Runs beside prepare, so it decides on its own what prepare will need: a video in 0_START, or a brief with links."""
    WORDS.mkdir(parents=True, exist_ok=True)
    (WORDS / "ready.txt").write_text(f"part {i} of {n}\n")   # the artifact exists even when there is nothing to do
    dropped = [l.strip() for l in (ROOT / "config" / "dropped.txt").read_text().splitlines() if l.strip() and not l.startswith("#")] if (ROOT / "config" / "dropped.txt").exists() else []
    for name, cpath in drive.campaigns():
        if name in dropped or (only and name != only) or (ROOT / "campaigns" / name / "words.json").exists():
            continue
        st = load_state(name)
        stage = drive.stages(cpath, create=False)
        (WORK / name).mkdir(parents=True, exist_ok=True)
        try:
            if not drive.files(stage["0_START"], VID_EXT) and not st.get("brief", {}).get("links"):
                log(f"{name}: no episode yet (prepare reads the brief first)")
                continue
            src = get_source(name, st, stage, ROOT / "campaigns" / name, for_audio=True)
            if not src or not has_speech(src):
                log(f"{name}: no source" if not src else f"{name}: no speech")
                continue
            out = WORDS / name / f"part_{i}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            r = pipeline.sh([pipeline.PY, str(pipeline.HERE / "transcribe.py"), str(src), str(out), "--part", f"{i}/{n}"],
                            WORK / name / f"transcribe_{i}.log", timeout=3 * 3600)
            log(f"{name}: part {i + 1}/{n} " + ("done" if out.exists() else f"FAILED (exit {r.returncode})"))
        except Exception as e:
            log(f"{name}: ERROR {type(e).__name__}: {str(e)[:160]}")


def wait_for_parts(name, n=TRANSCRIBE_PARTS, limit=50 * 60):
    """Prepare: the transcript parts of this campaign from the transcribe machines of the same run (artifacts
    words-0..n-1), polled with gh. None when a machine failed or timed out: prepare then transcribes itself."""
    run_id, repo = os.environ.get("GITHUB_RUN_ID"), os.environ.get("GITHUB_REPOSITORY", "")
    got, t0, waited, last_look = {}, time.time(), False, False
    while time.time() - t0 < limit:
        for i in range(n):
            if i in got:
                continue
            d = WORK / "parts" / str(i)
            r = subprocess.run(["gh", "run", "download", run_id, "-R", repo, "-n", f"words-{i}", "-D", str(d)], capture_output=True, text=True)
            if r.returncode == 0:
                got[i] = d / name / f"part_{i}.json"
            elif re.search(r"403|Resource not accessible|not logged|authentication", r.stderr):
                log(f"{name}: cannot read the run's artifacts ({r.stderr.strip()[-160:]}); transcribing here")
                return None
            elif not waited:
                log(f"{name}: parts not there yet ({r.stderr.strip().splitlines()[-1][:120] if r.stderr.strip() else 'no output'})")
        if len(got) == n:
            break
        # a transcribe machine that finished without an artifact is not coming
        r = subprocess.run(["gh", "run", "view", run_id, "-R", repo, "--json", "jobs", "--jq",
                            '[.jobs[] | select(.name | startswith("transcribe")) | .status] | map(select(. == "completed")) | length'],
                           capture_output=True, text=True)
        if r.stdout.strip().isdigit() and int(r.stdout.strip()) >= n:
            if last_look:
                break
            last_look = True   # one more look in 30 s: the last upload may still be landing
            time.sleep(30)
            continue
        if not waited:
            log(f"{name}: waiting for the transcript parts from {n} machines")
            waited = True
        time.sleep(20)
    parts = [got[i] for i in range(n) if i in got and got[i].exists()]
    if len(parts) == n:
        return parts
    log(f"{name}: {len(parts)} of {n} transcript parts arrived in {(time.time() - t0) / 60:.0f} min; transcribing here")
    return None


def get_watermark(name, st, stage):
    """The brand/show watermark a campaign requires (brief says "watermark", or a PNG named watermark/logo sits in
    0_START) -> WORK/<name>/watermark.png on this machine; render_clip keeps it on screen the whole clip. Several
    variants (black / white kits): the one with the most opaque pixels, it reads on any picture. None = no watermark."""
    dest = WORK / name / "watermark.png"
    if dest.exists():
        return dest
    imgs = [f for f in drive.files(stage["0_START"], IMG_EXT) if not f["Name"].lower().endswith("_thumbnail.png")]
    named = [f for f in imgs if re.search(r"watermark|logo|brand|badge", f["Name"], re.I)]
    cands = named or (imgs if st.get("brief", {}).get("watermark") else [])
    if not cands:
        if st.get("brief", {}).get("watermark") and not st.get("watermark_missing"):
            note(st, "the brief requires a watermark but no PNG is in 0_START: clips render without it, drop the watermark file in")
            st["watermark_missing"] = True
        return None
    from PIL import Image
    best, cover = None, -1.0
    for f in cands[:6]:
        try:
            local = drive.download(f["Path"], WORK / name / "wm_candidates" / f["Name"])
            im = Image.open(local).convert("RGBA")
            a = im.getchannel("A")
            c = sum(1 for v in a.getdata() if v > 40) / float(im.width * im.height)
        except Exception as e:
            note(st, f"watermark {f['Name'][:50]} unreadable ({type(e).__name__})")
            continue
        if c > cover:
            best, cover = (local, im), c
    if not best:
        return None
    local, im = best
    im.save(dest)
    if st.get("watermark") != local.name:
        note(st, f"watermark: {local.name} ({im.width}x{im.height}), kept on screen the whole clip, top of the picture")
        st["watermark"] = local.name
    return dest


def do_campaign(name, cpath, phase="all"):
    """phase 'all': cut on this machine. 'prepare': stop after the picks and return the render jobs."""
    st = load_state(name)
    cdir = ROOT / "campaigns" / name
    cdir.mkdir(parents=True, exist_ok=True)
    stage = drive.stages(cpath, create=False)
    (WORK / name).mkdir(parents=True, exist_ok=True)

    # 0_START: requirements -> brief
    if not st.get("brief"):
        reqs = [f for f in drive.files(stage["0_START"], REQ_EXT) if not is_bot_doc(f)]
        if not reqs:
            note(st, "waiting for the requirements file in 0_START")
            save_state(name, st)
            return
        stage = drive.stages(cpath)  # requirements are in: now make the campaign folder in 1_CHECK, 2_REDO, 3_APPROVED
        text = "\n\n".join(drive.text_of(f["Path"], f["Name"]) for f in reqs)
        # rules often live behind a link (Notion, Google Doc, a brand page): fetch those pages too
        import fetch_page
        fetched = []
        for url in dict.fromkeys(u.rstrip(".,:;)") for u in re.findall(r"https?://[^\s<>\"')\]]+", text)):
            # videos, podcasts and recordings are sources, not rule pages
            if re.search(r"youtube\.com|youtu\.be|tiktok\.com|instagram\.com|drive\.google\.com/|contentrewards\.com|we\.tl|wetransfer\.com|"
                         r"dropbox\.com|discord\.gg|discord\.com|spotify\.com|zoom\.us|rss\.com|podcast|apple\.com|x\.com|twitter\.com|\.media/|magazine\.com|tftc\.io", url):
                continue   # footage folders, transfers and chat invites are not rules pages
            try:
                page = fetch_page.fetch_text(url.rstrip(".,"))
            except Exception as e:
                page = f"({type(e).__name__}: {str(e)[:120]})"
            note(st, f"rules page {url}: {len(page)} chars" + ("" if len(page) > 200 else f" -> {page[:160]}"))
            if page and len(page) > 200:
                fetched.append(f"=== {url} ===\n{page[:20000]}")
        if fetched:
            text += "\n\n" + "\n\n".join(fetched)
            drive.write_doc("RULES (fetched by the bot)", "\n\n".join(fetched)[:60000], stage["0_START"])
        st["brief"] = briefer.parse(text)
        if fetched:   # handles and per-platform tags come from the requirements file itself, never from a fetched page's chatter
            own = briefer.parse(text.split("\n\n=== ")[0])
            st["brief"]["tags"], st["brief"]["tags_by_platform"] = own["tags"], own["tags_by_platform"]
        (cdir / "brief.json").write_text(json.dumps(st["brief"], indent=1))
        b = st["brief"]
        drive.write_doc("BRIEF", "What the bot read from the requirements:\n\n"
                        f"platforms: {', '.join(b['platforms']) or '?'}\nlength: {b['min_s']}-{b['max_s']} s\ntags: {' '.join(b['tags']) or 'none found'}\n"
                        f"rate: {b['rate_per_1k']} per 1k, min {b['min_payout']}, max {b['max_per_clip']}\nface in first: {b['face_first_s']} s\n"
                        f"video assigned: {'yes' if b['assigned_video'] else 'free choice'}\nwatermark: {'required (PNG from 0_START, on screen the whole clip)' if b.get('watermark') else 'no'}\n"
                        f"tags per platform: {b.get('tags_by_platform') or 'same everywhere'}\nlinks: {chr(10).join(b['links']) or 'none'}\n\nrules kept:\n- " + "\n- ".join(b["rules"][:30]), stage["0_START"])
        note(st, f"brief read: {len(b['rules'])} rules, {len(b['links'])} links, tags {b['tags']}")

    # 2_REDO: new critiques -> saved for the reviewer, clips re-picked
    seen = set(st.get("critiques_seen", []))
    for f in drive.files(stage["2_REDO"], REQ_EXT):
        key = f"{f['Path']}@{f.get('ModTime')}"
        if key in seen:
            continue
        txt = drive.text_of(f["Path"], f["Name"])
        (cdir / "critiques").mkdir(exist_ok=True)
        (cdir / "critiques" / f"{datetime.now(timezone.utc):%Y%m%d-%H%M}_{f['Name']}.md").write_text(txt)
        seen.add(key)
        st["needs_redo"] = True
        note(st, f"critique read: {f['Name']} ({len(txt)} chars); clips will be re-picked")
    st["critiques_seen"] = sorted(seen)

    # 3_APPROVED: post kits
    approved = drive.files(stage["3_APPROVED"], VID_EXT)
    kits = st.get("kits", {})
    clips = {c["mp4"]: c for c in st.get("clips", [])}
    # a clip approved since the last kit, or a thumbnail whose look / pins changed: the WHOLE kit is written again, for
    # every approved clip (the kit is one doc; writing only the new clip's entry wiped the earlier clips' entries)
    changed = [f for f in approved if f["Path"] not in kits
               or (f["Name"] in clips and clips[f["Name"]].get("thumb_sig") != thumb_sig(cdir, clips[f["Name"]]))]
    if changed:
        new_kits = approved
        text = [f"POST KIT  ({now()})", "", "One platform per clip, by what the clip is about (YouTube = business/money, Instagram = celebrity/drama, TikTok = entertainment).", ""]
        if any(f["Name"] in clips and not clips[f["Name"]].get("lane") for f in new_kits):
            # clips kept before lanes existed: assign now from their words
            old = [clips[f["Name"]] for f in new_kits if f["Name"] in clips and not clips[f["Name"]].get("lane")]
            for c, (lane, _) in zip(old, lanes.assign([{"hook": c["hook"], "text": c.get("text", c.get("caption", "")), "style": st["brief"].get("style", "")} for c in old])):
                c["lane"] = lane
        for f in new_kits:
            c = clips.get(f["Name"], {})
            lane = c.get("lane") or (st["brief"].get("platforms") or ["youtube"])[0]
            thumb_name = ensure_thumbnail(name, st, stage, cdir, f, c)
            text.append(post_kit.kit(f["Name"], c.get("hook", Path(f["Name"]).stem.replace("-", " ")), st["brief"], [lane], caption=c.get("caption", ""), thumb=thumb_name,
                                     options=f"{Path(f['Name']).stem}_thumbnail_options.jpg" if thumb_name else ""))
            text.append("")
            kits[f["Path"]] = f["Name"]
        drive.write_doc("POST KIT", "\n".join(text), stage["3_APPROVED"])
        st["kits"] = kits
        note(st, f"post kit written for {len(new_kits)} approved clip(s) ({len(changed)} new or changed)")

    # 1_CHECK: cut when there is nothing there yet, or after a critique
    if st.get("clips") and not st.get("needs_redo"):
        save_state(name, st)
        return
    if not st.get("needs_redo") and st.get("empty_runs", 0) >= 3:
        # three runs with nothing kept: the material (or the brief) is the problem, not the dice; rendering the same
        # episode every 5 hours only burns minutes. A note in 2_REDO or a plan.json starts it again.
        if not st.get("empty_told"):
            note(st, "3 runs kept nothing: waiting for a note in 2_REDO or a plan.json before trying again")
            st["empty_told"] = True
        save_state(name, st)
        return
    plan = json.loads((cdir / "plan.json").read_text()) if (cdir / "plan.json").exists() else {}
    if plan.get("brief_overrides"):      # the reviewer can pin fields the parser got wrong (tags, rules, lengths)
        st["brief"].update(plan["brief_overrides"])
    if plan.get("brand_clips"):          # brand mode: scripts + voice over the campaign's own footage
        import brand_mode
        footage = get_footage(name, st, stage)
        if not footage:
            note(st, "brand mode: waiting for the footage in 0_START")
            save_state(name, st)
            return
        t0 = time.time()
        kept, summary = brand_mode.run(WORK / name, footage, st["brief"], plan, campaign=name, log=log)
        publish(name, st, stage, kept, summary, t0)
        return
    src = get_source(name, st, stage, cdir)
    if not src:
        save_state(name, st)
        return
    get_watermark(name, st, stage)   # WORK/<name>/watermark.png: pipeline.one_clip hands it to render_clip
    if not has_speech(src):
        if not st.get("needs_scripts"):
            note(st, "footage has no speech: brand mode needs scripts (brand_clips in campaigns/<c>/plan.json)")
        st["needs_scripts"] = True
        save_state(name, st)
        return
    words = cdir / "words.json"
    if not words.exists() and phase == "prepare" and os.environ.get("GITHUB_RUN_ID"):
        # the 4 transcribe machines run beside this one (run.yml): map the graphics meanwhile, then take their parts
        gfx = WORK / name / "gfx.json"
        if not gfx.exists():
            pipeline.sh([pipeline.PY, str(pipeline.HERE / "graphics_map.py"), str(src), str(gfx)], WORK / name / "gfx.log")
        parts = wait_for_parts(name)
        if parts:
            pipeline.sh([pipeline.PY, str(pipeline.HERE / "transcribe.py"), "--merge", str(words), *parts], WORK / name / "merge.log")
            if words.exists():
                note(st, f"transcript merged from {len(parts)} machines")
    if not words.exists():
        note(st, "transcribing the whole episode")
    # moments rico already saw, plus moments rendered and dropped before: the scorecard moves on to new ones
    used = [(c["start"], c["end"]) for c in st.get("used_moments", []) + st.get("tried_moments", [])]
    t0 = time.time()
    if phase == "prepare":
        specs, origin, wpath, notes = pipeline.prepare(WORK / name, src, st["brief"], words if words.exists() else None, campaign=name,
                                                       log=log, used=used, plan_dir=cdir)
        if not words.exists():
            shutil.copy(wpath, words)
        d = PREP / name
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy(wpath, d / "words.json")
        if (WORK / name / "gfx.json").exists():
            shutil.copy(WORK / name / "gfx.json", d / "gfx.json")
        (d / "notes.json").write_text(json.dumps(notes))
        slots = min(MATRIX_MAX, len(specs))
        jobs = [{"campaign": name, "cpath": cpath, "spec": sp, "fallbacks": specs[slots:][i::slots] if slots else [], "origin": origin, "t0": t0}
                for i, sp in enumerate(specs[:slots])]
        note(st, f"{len(jobs)} candidate(s) picked ({origin}), {len(specs) - len(jobs)} fallback(s); rendering on {len(jobs)} machines with grade-and-retry")
        save_state(name, st)
        return jobs
    kept, summary, tried = pipeline.run(WORK / name, src, st["brief"], words if words.exists() else None, campaign=name, log=log,
                                        used=used, plan_dir=cdir)   # cdir holds the reviewer's plan.json; used = moments rico already saw
    remember_moments(st, kept, tried)
    if (WORK / name / "words.json").exists() and not words.exists():
        shutil.copy(WORK / name / "words.json", words)   # /tmp and the repo are different disks on the runner
    publish(name, st, stage, kept, summary, t0)


def remember_moments(st, kept, tried=()):
    """used_moments: what rico saw in 1_CHECK (last 30). tried_moments: what was rendered and dropped (last 60).
    Both keep one entry per (start, end): the old list filled its cap with the same moment repeated after redos."""
    def add(key, items, cap):
        have = {(round(m["start"], 2), round(m["end"], 2)): m for m in st.get(key, [])}
        for c in items:
            for p in c.get("parts", []):
                have[(round(p[0], 2), round(p[1], 2))] = {"start": p[0], "end": p[1], "hook": c.get("hook", "")}
        st[key] = list(have.values())[-cap:]
    add("used_moments", kept, 30)
    seen = {(round(p[0], 2), round(p[1], 2)) for c in kept for p in c.get("parts", [])}
    add("tried_moments", [r for r in tried if not any((round(p[0], 2), round(p[1], 2)) in seen for p in r.get("parts", []))], 60)


def render_job(n):
    """One candidate on one machine: source from Drive (cache), render, QA, judge -> OUT/<n>/."""
    jobs = json.loads((PREP / "jobs.json").read_text())
    j = jobs[n]
    name, spec = j["campaign"], j["spec"]
    st = load_state(name)
    stage = drive.stages(j["cpath"], create=False)
    cdir = ROOT / "campaigns" / name
    work = WORK / name
    work.mkdir(parents=True, exist_ok=True)
    for f in ("words.json", "gfx.json"):
        if (PREP / name / f).exists():
            shutil.copy(PREP / name / f, work / f)
    words = work / "words.json"
    spec["words"] = str(words)
    src = get_source(name, st, stage, cdir)
    if not src:
        raise RuntimeError("source not available on the render machine")
    spec["source"] = str(src)
    get_watermark(name, st, stage)
    (work / "renders").mkdir(exist_ok=True)
    lane = [spec] + j.get("fallbacks", [])
    for sp in lane:
        sp["words"], sp["source"] = str(words), str(src)
    res, tries = pipeline.try_until(lane, work, src, words, f"c{n + 1:02d}", log=log)
    res = res or {"hook": spec["hook"], "error": "no render finished", "ok": False, "judge": 0, "qa": "FAIL", "fails": [], "why": "", "parts": spec.get("parts", []), "dur": 0}
    res["tries"] = [f"{Path(str(r.get('folder', r['hook']))).name}: qa {r.get('qa')} judge {r.get('judge')} ({r.get('areas', '')}) {'; '.join(r.get('fails', [])[:2])}" for r in tries]
    out = OUT / str(n)
    out.mkdir(parents=True, exist_ok=True)
    if res.get("folder"):
        fname = Path(res["folder"]).name
        shutil.copytree(res["folder"], out / fname, dirs_exist_ok=True)
        res["folder"], res["mp4"] = fname, fname + "/" + Path(res["mp4"]).name
        if res.get("thumb"):    # thumbnail.png sits inside the clip folder; without this the PNG never reached 1_CHECK
            res["thumb"] = fname + "/" + Path(res["thumb"]).name
    (out / "result.json").write_text(json.dumps(res, default=str))
    log(f"done: qa {res.get('qa')} judge {res.get('judge')} {res.get('minutes', '?')} min" + (f"  {res['error']}" if res.get("error") else ""))


def collect():
    """All render results -> keep up to 3 per campaign -> 1_CHECK + SUMMARY, state."""
    jobs = json.loads((PREP / "jobs.json").read_text())
    by = {}
    for n, j in enumerate(jobs):
        by.setdefault(j["campaign"], []).append((n, j))
    for name, items in by.items():
        st = load_state(name)
        try:
            stage = drive.stages(items[0][1]["cpath"], create=False)
            work = WORK / name
            work.mkdir(parents=True, exist_ok=True)
            notes = json.loads((PREP / name / "notes.json").read_text()) if (PREP / name / "notes.json").exists() else []
            results = []
            for n, j in items:
                d = next((x for x in (OUT / str(n), OUT / f"clip-{n}") if (x / "result.json").exists()), None)
                if not d:
                    results.append({"hook": j["spec"]["hook"], "error": "render machine returned nothing (timeout or crash)"})
                    continue
                res = json.loads((d / "result.json").read_text())
                if res.get("folder"):
                    res["folder"] = str(d / res["folder"]); res["mp4"] = str(d / res["mp4"])
                    if res.get("thumb"):
                        res["thumb"] = str(d / res["thumb"])
                for t in res.get("tries", [])[:-1]:
                    notes.append("TRY   " + t)
                results.append(res)
            results.sort(key=lambda r: (-int(bool(r.get("ok"))), -(r.get("judge") or 0)))   # best clips first
            kept, notes = pipeline.decide(results, work, [], notes)
            mins = [r.get("minutes", 0) for r in results if r.get("minutes")]
            notes.append(f"{len(kept)} clip(s) kept of {len(results)} rendered on {len(results)} machines, "
                         f"longest render {max(mins) if mins else 0:.1f} min")
            summary = "\n".join(notes)
            log(summary)
            remember_moments(st, kept, [r for r in results if not r.get("error")])
            publish(name, st, stage, kept, summary, items[0][1].get("t0") or time.time())
        except Exception as e:
            note(st, f"ERROR {type(e).__name__}: {str(e)[:200]}")
            save_state(name, st)


def publish(name, st, stage, kept, summary, t0):
    """Kept clips -> 1_CHECK/<campaign>/ with the SUMMARY doc; state remembers them.
    Clips from an earlier run are moved to _trash first (nothing is deleted), so 1_CHECK never mixes
    old and new renders (2026-10-28: run 5 left run 4's clips beside its own)."""
    if kept:
        try:
            r = drive.root()
            for f in drive.files(stage["1_CHECK"], VID_EXT + (".png", ".jpg")):   # clips and their thumbnail PNGs / options sheets
                drive.move(f["Path"], f"{r}/_trash/1_CHECK_{name}_{f['Name']}")
        except Exception as e:
            log(f"could not clear old clips from 1_CHECK: {e}")
    for k, c in enumerate(kept, 1):
        drive.upload(c["mp4"], stage["1_CHECK"], name=f"{k:02d}_{Path(c['mp4']).name.split('_', 1)[-1]}")
        if c.get("thumb") and Path(c["thumb"]).exists():
            drive.upload(c["thumb"], stage["1_CHECK"], name=f"{k:02d}_{Path(c['mp4']).stem.split('_', 1)[-1]}_thumbnail.png")
            opts = Path(c["thumb"]).with_name("thumbnail_options.jpg")
            if opts.exists():
                drive.upload(str(opts), stage["1_CHECK"], name=f"{k:02d}_{Path(c['mp4']).stem.split('_', 1)[-1]}_thumbnail_options.jpg")
    body = [f"SUMMARY  ({now()}, {(time.time() - t0) / 60:.0f} min)", "", f"{len(kept)} clip(s) in 1_CHECK. Max 3 per campaign.", ""]
    for k, c in enumerate(kept, 1):
        body += [f"{k:02d}  {c['hook']}  ({c['dur']} s, judge {c['judge']})", f"    post on: {c.get('lane', '?').upper()} ({lanes.handle(c.get('lane', ''))})",
                 f"    why: {c['why']}", "    captions:", *("    " + l for l in c["captions"].splitlines()[:40]), ""]
    body += ["Run notes:", summary, "", "Approve: drag the mp4 to 3_APPROVED. Change: put a Word doc with your notes in 2_REDO."]
    drive.write_doc("SUMMARY", "\n".join(body), stage["1_CHECK"])
    st["clips"] = [{"mp4": f"{k:02d}_{Path(c['mp4']).name.split('_', 1)[-1]}", "hook": c["hook"], "judge": c["judge"], "dur": c["dur"],
                    "caption": c.get("caption", ""), "lane": c.get("lane", ""), "text": " ".join(c.get("captions", "").split()),
                    "parts": c.get("parts", [])} for k, c in enumerate(kept, 1)]
    st["needs_redo"] = False
    st["empty_runs"] = 0 if kept else st.get("empty_runs", 0) + 1
    if kept:
        st["empty_told"] = False
    note(st, f"{len(kept)} clip(s) uploaded to 1_CHECK")
    save_state(name, st)

def main(only=None, phase="all"):
    rt = drive.root()
    log(f"CLIPPING root {rt}")
    dropped = [l.strip() for l in (ROOT / "config" / "dropped.txt").read_text().splitlines() if l.strip() and not l.startswith("#")] if (ROOT / "config" / "dropped.txt").exists() else []
    for d in dropped:   # campaigns rico dropped: their folders go to _trash, their state is forgotten
        moved = drive.drop(d)
        if moved:
            log(f"dropped {d}: moved {', '.join(moved)} to _trash")
        if state_path(d).exists():
            shutil.rmtree(state_path(d).parent, ignore_errors=True)
    camps = [c for c in drive.campaigns() if c[0] not in dropped]
    if only:
        camps = [c for c in camps if c[0] == only]
    jobs = []
    for name, cpath in camps:
        try:
            got = do_campaign(name, cpath, phase)
            if phase == "prepare" and got:
                jobs += got
        except Exception as e:  # one campaign must not stop the others
            st = load_state(name)
            note(st, f"ERROR {type(e).__name__}: {str(e)[:200]}")
            save_state(name, st)
    if phase == "prepare":
        PREP.mkdir(parents=True, exist_ok=True)
        (PREP / "jobs.json").write_text(json.dumps(jobs, default=str))
        log(f"{len(jobs)} render job(s)")
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"count={len(jobs)}\njobs={json.dumps(list(range(len(jobs))))}\n")
    # the campaign scan runs on its own hourly workflow (scan.yml); it used to run here too, and the two commits
    # of data/scan_seen.json raced (2026-10-29 audit)


if __name__ == "__main__":
    a = sys.argv[1:]
    ph = a[a.index("--phase") + 1] if "--phase" in a else "all"
    if ph == "render":
        render_job(int(a[a.index("--job") + 1]))
    elif ph == "transcribe":
        transcribe_job(int(a[a.index("--part") + 1]), int(a[a.index("--parts") + 1]) if "--parts" in a else TRANSCRIBE_PARTS,
                       a[0] if a and not a[0].startswith("--") else None)
    elif ph == "collect":
        collect()
    else:
        main(a[0] if a and not a[0].startswith("--") else None, ph)
