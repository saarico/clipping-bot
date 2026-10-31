"""Camera Operator: frames every piece of every shot into the 9:16 picture.

In:  edits.json pieces (source start, end, output offset) + the spec's overlays / focus / video_swap.
Out: video.mp4 (picture only, no captions) and frame.json, one record per rendered segment:
     {from, to (output s), src (source s), layout, zoom, face [cx, cy, size] or null, pan_keys, overlay}.
Owns: who is on screen, the crop window, pans, punch-ins, overlay layouts. Never touches sound or text.
"""
from render_clip import (CINE_MIN_FACE, FPS, HC, HOOK_SECS, SRC_H, SRC_W, W, Framer, analyze_shots, build_filter,
                         card_source, deflash, pan_keys, people, profiles, run, sub_ranges, talker)


def shoot(spec, src, pieces, overlays, focus, marks, has_teaser, tmp):
    """Renders the picture into tmp/video.mp4. Returns (layouts, frames): layouts = [(from, to, "face+zoom"), ...]."""
    framer = Framer()
    whole_when_lost = not profiles.profile(spec.get("style"))["cards"]   # cinematic / stream / performance
    last_cx, last_shot = None, None
    wide_pair = None   # the two small faces of the wide two-shot, once found in this render
    segs, layouts, frames = [], [], []
    for pi, (s, e, poff) in enumerate(pieces):
        # pieces alternate a light punch-in (1.0 / 1.06), so every join between two moments or
        # across a cut pause reads as an edit, not a glitch
        piece_zoom = (1.0 if pi % 2 == 0 else 1.06) if not whole_when_lost else 1.0   # movies: no punch-in games between pieces
        for sh in analyze_shots.shots(src, s, e):
            subs = sub_ranges(max(sh["start"], s), min(sh["end"], e), marks)
            for w in spec.get("video_swap", []):   # always split where a swap ends
                subs = [r for a, b in subs for r in (((a, w[1]), (w[1], b)) if a < w[1] < b else ((a, b),))]
            for a, b in subs:
                n = round((b - a) * FPS)
                if n <= 0:
                    continue
                mid = (a + b) / 2
                # stray shot after a jump: show other frames of the speaker instead (audio stays)
                sw = next((w for w in spec.get("video_swap", []) if w[0] - 0.05 <= a < w[1]), None)
                vs = sw[2] + (a - sw[0]) if sw else a
                ov = next((o for o in overlays if o["from"] <= mid < o["to"]), None)
                zoom = 1.17 if any(f[0] <= mid < f[1] for f in focus) else piece_zoom
                keys, panel_w, small_used, tb = None, 630, False, None
                same_shot = last_shot is not None and abs(last_shot - sh["start"]) < 0.01
                if ov and ov["style"] == "hide" and not people(analyze_shots.faces_in(src, a, b), box=ov["box"]):
                    ov = None      # nobody to crop the strip away from (wide shot, b-roll): frame as usual
                if ov:
                    ppl = people(analyze_shots.faces_in(src, a, b), box=ov["box"])[:1]
                    lay = ov["style"]
                    t_in, t_out = a - ov["from"], ov["to"] - a
                else:
                    part_of_shot = (b - a) < (sh["end"] - sh["start"]) - 0.1   # e.g. after a b-roll
                    # a piece of a long shot gets its own face position (the speaker may have moved)
                    ppl = people(analyze_shots.faces_in(src, vs, vs + b - a) if sw or part_of_shot else sh["faces"])
                    if len(ppl) == 2:
                        ppl = [talker(ppl)]   # a two-person shot: crop on whoever is speaking, never a split (one look, one caption spot)
                    if not ppl:
                        # nobody big: the wide two-shot? (faces ~45 px) -> stacked split on both people.
                        # If the detector misses one of them (dark set, a turned head) fall back to the
                        # pair found earlier in this render, then to the spec's "wide_split", so the
                        # window never lands on an empty room (rico, 2026-10-26: v1 MM-005/006 showed
                        # 6 s of empty room where the wide shot was cropped down the middle).
                        # the whole shot, not this piece of it: the pair does not move and the result is cached
                        small = analyze_shots.small_faces(src, *((vs, vs + b - a) if sw else (sh["start"], sh["end"])))
                        small_used = True
                        fixed = [tuple(p) for p in spec.get("wide_split", [])]
                        if len(small) == 2 and len(fixed) == 2 and any(
                                min(abs(f[0] - q[0]) for f in fixed) > 0.12 for q in small):
                            small = []      # a face in the show's photo card + a false hit: not the two people
                        if len(small) == 2 and abs(small[0][0] - small[1][0]) > 0.3:
                            ppl, panel_w = small, 520
                            wide_pair = list(small)
                        else:
                            pair = [] if whole_when_lost else (wide_pair or fixed)   # a movie's wide shot is not the podcast's two seats
                            if len(pair) == 2:
                                ppl, panel_w = pair, 520
                            elif len(small) == 1:
                                ppl = small
                    if len(ppl) == 2:
                        # the wide two-shot of a talking show: no stacked split any more (rico 2026-10-31: the captions
                        # jumped to the seam). Crop on whoever talks (mouth motion from the 720p pass when it has it) and
                        # punch in so the face is not a dot; capped so the picture stays sharp enough
                        fine = people(analyze_shots.faces_in(src, vs, vs + b - a, hi=True), min_size=0.03, max_size=0.6)
                        ppl = [talker(fine if len(fine) == 2 else ppl)]
                        if ppl[0][2] < 0.10:
                            # up to 1.6x (was 1.35): a 1080p interview filmed from across the room (Spotlight, faces 4-7%
                            # of the picture, 2026-10-31) is otherwise a dot; beyond 1.6x the picture goes soft
                            zoom = max(zoom, min(1.6, 0.11 / max(ppl[0][2], 0.03)))
                    lay = "face" if ppl else "wide"
                    t_in = t_out = 0
                    if whole_when_lost:
                        # movies, streams, concerts: ONE 9:16 look for the whole clip (rico, 2026-10-28: "the screen
                        # keeps switching between 16:9 and 9:16, horrible"; "not focusing on actors"). The window
                        # follows the actors and punches in on wide shots; a two-shot is cropped on whoever talks,
                        # never split; burned-in text that fits the window is centred (wide credit cards at the
                        # clip's edges were trimmed off by trim_cards).
                        # YuNet sees small and turned faces: take any face from 4% of the width up
                        allf = analyze_shots.faces_in(src, vs, vs + b - a, hi=True)   # 720p search: small faces count
                        ppl = people(allf, min_size=CINE_MIN_FACE, max_size=0.6)
                        # burned-in text wins only when nobody is on screen, or when it is a real card
                        # (a third of the width or more): the globe's map labels and a video-call window
                        # pulled the crop off Rockwell in c01 (2026-10-29)
                        tb = analyze_shots.text_box(src, vs, vs + b - a) if not ppl or ppl[0][2] < 0.10 else None
                        if tb and ppl and (tb[2] - tb[0]) < 0.35:
                            tb = None
                        if tb and not ppl and (tb[2] - tb[0]) < 0.30 and abs((tb[0] + tb[2]) / 2 - 0.5) > 0.15:
                            tb = None      # a narrow "text" off to one side with nobody around is a window grid, not a card (c02)
                        if tb:
                            ppl = [((tb[0] + tb[2]) / 2, (tb[1] + tb[3]) / 2, 0.2)]
                            lay, zoom = "face", 1.0          # centred on the text, never zoomed (the detector can miss letters)
                        elif ppl:
                            if len(ppl) == 2:
                                ppl = [talker(ppl)]
                            lay = "face"
                            zoom = max(zoom, min(1.4, max(1.0, 0.16 / max(ppl[0][2], 0.02))))
                        else:
                            pp = analyze_shots.people_in(src, vs, vs + b - a)
                            if pp:
                                ppl, lay, zoom = [(pp[0][0], pp[0][1], 0.2)], "face", 1.0   # a person, no face: frame the body
                            else:
                                lay = "wide"
                        zoom = min(1.5, zoom * spec.get("zoom_boost", 1.0))
                if lay in ("face", "side", "bottom", "banner", "hide") and ppl and ppl[0][2] >= (CINE_MIN_FACE if whole_when_lost else 0.1) and not (whole_when_lost and tb):
                    # movies: the dead zone is 6% of the WINDOW width (a zoomed-in window is narrow: 8% of the
                    # source width was a third of the picture, which left Rockwell at the edge, c01 2026-10-29)
                    win_w = (SRC_H / zoom) * W / HC / SRC_W
                    keys, _ = pan_keys(src, vs, vs + b - a, box=ov["box"] if ov else None,
                                       start_cx=last_cx if same_shot else None,
                                       min_size=CINE_MIN_FACE if whole_when_lost else 0.10,
                                       dead=0.06 * win_w if whole_when_lost else 0.10,
                                       anchor=ppl[0][0] if whole_when_lost else None,
                                       smooth=1 if whole_when_lost else 2,   # movies: 0.75 s window, less lag behind a walking actor
                                       hi=whole_when_lost, hold=0 if whole_when_lost else 4)
                    if keys:
                        ppl = [(keys[0][1], ppl[0][1], ppl[0][2])] + ppl[1:]
                        last_cx = keys[-1][1]
                if ppl and not keys:
                    ppl = [(framer.x(p[0]), p[1], p[2]) for p in ppl]
                last_shot = sh["start"]
                extra, card_pre = [], None
                if ov and ov.get("card_window"):
                    c_ss, card_pre = card_source(ov, a, n)
                    extra = ["-ss", f"{c_ss:.3f}", "-i", src]
                if ov and ov.get("hard_out"):
                    t_out = 1e6   # leave on the camera cut instead of sliding out (no half-gone card)
                graph = build_filter(lay, ppl, zoom, ov, t_in, t_out, card_pre, keys=keys, panel_w=panel_w)
                fades = []
                if spec.get("teaser_cut"):
                    pass   # straight cut out of the teaser, no dip
                elif has_teaser and pi == 0 and abs(b - e) < 0.05:
                    fades.append(f"fade=out:st={max(n / FPS - 0.15, 0):.3f}:d=0.15:color=black")
                if has_teaser and pi == 1 and abs(a - s) < 0.05:
                    fades.append("fade=in:st=0:d=0.15:color=black")
                if fades:
                    graph = graph[:-3] + "[pre];[pre]" + ",".join(fades) + "[v]"
                out = tmp / f"v{len(segs):03d}.mp4"
                run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{vs:.3f}", "-i", src, *extra,
                     "-filter_complex", graph, "-map", "[v]", "-an", "-r", str(FPS), "-frames:v", str(n),
                     "-c:v", "libx264", "-preset", "ultrafast", "-crf", "14", "-pix_fmt", "yuv420p", str(out)])
                o = poff + (a - s)
                layouts.append((o, o + n / FPS, lay + ("+zoom" if zoom > 1 and lay == "face" else "")))
                frames.append({"from": round(o, 3), "to": round(o + n / FPS, 3), "src": round(vs, 3), "layout": lay,
                               "zoom": round(zoom, 3), "face": [round(v, 4) for v in ppl[0]] if ppl else None,
                               "pan_keys": len(keys or []), "overlay": ov["style"] if ov else None})
                if o < HOOK_SECS and lay == "face" and ppl:
                    # where the top of the face lands in the 1080x1920 picture while the hook text shows (build_ass
                    # moves the hook to the bottom when a high-framed face would sit under it, 2026-10-31)
                    ch = min(int(SRC_H / zoom), SRC_H) // 2 * 2
                    y0 = 0 if ch == SRC_H else int(min(max(ppl[0][1] * SRC_H - ch * 0.45, 0), SRC_H - ch))
                    face_top = (ppl[0][1] * SRC_H - ppl[0][2] * SRC_W * 0.55 - y0) * HC / ch
                    spec["_face_top"] = min(spec.get("_face_top", 9e9), face_top)
                segs.append(out)
    (tmp / "list.txt").write_text("".join(f"file '{p}'\n" for p in segs))
    run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"),
         "-c", "copy", str(tmp / "video.mp4")])
    deflash(tmp / "video.mp4")
    return layouts, frames
