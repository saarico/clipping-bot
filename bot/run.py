"""One pass over Drive. Runs every 5 hours on GitHub (workflow run.yml) or by hand:

  python3 bot/run.py [campaign folder name]

For every folder under CLIPPING/:
  0_START   requirements file -> brief.json; episode.mp4 (or a YouTube link in the brief) -> transcript
  1_CHECK   <- up to 3 clips + SUMMARY doc, once the transcript and the plan exist
  2_REDO    rico's critique docs -> saved to campaigns/<c>/critiques/ for the reviewer; clips re-picked
  3_APPROVED  each clip gets its POST KIT entry (title, description, tags, rules to re-check)
State lives in campaigns/<c>/state.json (committed by the workflow). Videos never enter git.
"""
import json
import os
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

WORK = Path(os.environ.get("CLIP_WORK", "/tmp/clipwork"))
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


def is_gdoc(f):
    return f["mimeType"] == drive.GDOC


def get_source(name, st, stage, cdir):
    """Episode file: from 0_START, else yt-dlp on the brief's first link (best effort)."""
    dest = WORK / name / "episode.mp4"
    if dest.exists():
        return dest
    vids = [f for f in drive.children(stage["0_START"]) if f["name"].lower().endswith(VID_EXT)]
    if vids:
        note(st, f"downloading {vids[0]['name']} from 0_START")
        return drive.download(vids[0]["id"], dest)
    links = st.get("brief", {}).get("links", [])
    if links and not st.get("download_failed"):
        note(st, f"trying to download {links[0]} (yt-dlp)")
        r = subprocess.run(["yt-dlp", "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b", "--no-playlist",
                            "-o", str(dest), links[0]], capture_output=True, text=True, timeout=3600)
        if dest.exists():
            return dest
        st["download_failed"] = True
        msg = (r.stderr or "")[-300:].replace("\n", " ")
        note(st, "download blocked; asked rico for the file")
        drive.write_doc("NEEDS THE VIDEO", f"GitHub could not download the episode ({msg}).\n\nPlease drop the episode as episode.mp4 into this 0_START folder. The bot picks it up on its next run (every 5 hours).", stage["0_START"])
    return None


def do_campaign(name, cid):
    st = load_state(name)
    cdir = ROOT / "campaigns" / name
    cdir.mkdir(parents=True, exist_ok=True)
    stage = drive.stages(cid)
    (WORK / name).mkdir(parents=True, exist_ok=True)

    # 0_START: requirements -> brief
    if not st.get("brief"):
        reqs = [f for f in drive.children(stage["0_START"]) if f["name"].lower().endswith(REQ_EXT) or is_gdoc(f)]
        reqs = [f for f in reqs if f["name"] not in ("NEEDS THE VIDEO", "BRIEF")]
        if not reqs:
            note(st, "waiting for the requirements file in 0_START")
            save_state(name, st)
            return
        text = "\n\n".join(drive.text_of(f["id"], f["name"]) for f in reqs)
        st["brief"] = briefer.parse(text)
        (cdir / "brief.json").write_text(json.dumps(st["brief"], indent=1))
        b = st["brief"]
        drive.write_doc("BRIEF", "What the bot read from the requirements:\n\n"
                        f"platforms: {', '.join(b['platforms']) or '?'}\nlength: {b['min_s']}-{b['max_s']} s\ntags: {' '.join(b['tags']) or 'none found'}\n"
                        f"rate: {b['rate_per_1k']} per 1k, min {b['min_payout']}, max {b['max_per_clip']}\nface in first: {b['face_first_s']} s\n"
                        f"video assigned: {'yes' if b['assigned_video'] else 'free choice'}\nlinks: {chr(10).join(b['links']) or 'none'}\n\nrules kept:\n- " + "\n- ".join(b["rules"][:30]), stage["0_START"])
        note(st, f"brief read: {len(b['rules'])} rules, {len(b['links'])} links, tags {b['tags']}")

    # 2_REDO: new critiques -> saved for the reviewer, clips re-picked
    seen = set(st.get("critiques_seen", []))
    for f in drive.children(stage["2_REDO"]):
        if f["id"] in seen or not (is_gdoc(f) or f["name"].lower().endswith(REQ_EXT)):
            continue
        txt = drive.text_of(f["id"], f["name"])
        (cdir / "critiques").mkdir(exist_ok=True)
        (cdir / "critiques" / f"{datetime.now(timezone.utc):%Y%m%d-%H%M}_{f['name']}.md").write_text(txt)
        seen.add(f["id"])
        st["needs_redo"] = True
        note(st, f"critique read: {f['name']} ({len(txt)} chars); clips will be re-picked")
    st["critiques_seen"] = sorted(seen)

    # 3_APPROVED: post kits
    approved = [f for f in drive.children(stage["3_APPROVED"]) if f["name"].lower().endswith(VID_EXT)]
    kits = st.get("kits", {})
    new_kits = [f for f in approved if f["id"] not in kits]
    if new_kits:
        hooks = {Path(c["mp4"]).name: c["hook"] for c in st.get("clips", [])}
        text = [f"POST KIT  ({now()})", ""]
        for f in new_kits:
            text.append(post_kit.kit(f["name"], hooks.get(f["name"], Path(f["name"]).stem.replace("-", " ")), st["brief"], st["brief"].get("platforms") or ["youtube"]))
            text.append("")
            kits[f["id"]] = f["name"]
        drive.write_doc("POST KIT", "\n".join(text), stage["3_APPROVED"])
        st["kits"] = kits
        note(st, f"post kit written for {len(new_kits)} approved clip(s)")

    # 1_CHECK: cut when there is nothing there yet, or after a critique
    if st.get("clips") and not st.get("needs_redo"):
        save_state(name, st)
        return
    src = get_source(name, st, stage, cdir)
    if not src:
        save_state(name, st)
        return
    words = cdir / "words.json"
    if not words.exists():
        note(st, "transcribing the whole episode")
    used = [(c["start"], c["end"]) for c in st.get("used_moments", [])]
    t0 = time.time()
    kept, summary = pipeline.run(WORK / name, src, st["brief"], words if words.exists() else None, campaign=name, log=log)
    if (WORK / name / "words.json").exists() and not words.exists():
        (WORK / name / "words.json").replace(words)
    for k, c in enumerate(kept, 1):
        drive.upload(c["mp4"], stage["1_CHECK"], name=f"{k:02d}_{Path(c['mp4']).name.split('_', 1)[-1]}")
    body = [f"SUMMARY  ({now()}, {(time.time() - t0) / 60:.0f} min)", "", f"{len(kept)} clip(s) in 1_CHECK. Max 3 per campaign.", ""]
    for k, c in enumerate(kept, 1):
        body += [f"{k:02d}  {c['hook']}  ({c['dur']} s, judge {c['judge']})", f"    why: {c['why']}", "    captions:", *("    " + l for l in c["captions"].splitlines()[:40]), ""]
    body += ["Run notes:", summary, "", "Approve: drag the mp4 to 3_APPROVED. Change: put a Word doc with your notes in 2_REDO."]
    drive.write_doc("SUMMARY", "\n".join(body), stage["1_CHECK"])
    st["clips"] = [{"mp4": f"{k:02d}_{Path(c['mp4']).name.split('_', 1)[-1]}", "hook": c["hook"], "judge": c["judge"], "dur": c["dur"]} for k, c in enumerate(kept, 1)]
    st["needs_redo"] = False
    note(st, f"{len(kept)} clip(s) uploaded to 1_CHECK")
    save_state(name, st)


def main(only=None):
    rt = drive.root()
    log(f"CLIPPING root {rt}")
    camps = drive.campaigns()
    if only:
        camps = [c for c in camps if c[0] == only]
    for name, cid in camps:
        try:
            do_campaign(name, cid)
        except Exception as e:  # one campaign must not stop the others
            st = load_state(name)
            note(st, f"ERROR {type(e).__name__}: {str(e)[:200]}")
            save_state(name, st)
    try:
        import campaign_scan
        campaign_scan.main()
    except Exception as e:
        log(f"campaign scan skipped: {type(e).__name__}: {str(e)[:120]}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
