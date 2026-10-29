# Change log: every rule rico set and what changed in the bot

Newest first. Each entry: what rico said, the rule, and where it lives in the code. The living rule book is
RULES.md; the acceptance gates are scorecards/acceptance.md.

## 2026-10-29 (03:50 UTC): women in thumbnails, rico picks frames by number
- rico: "number 2 choose option 4" and "I think females get more clicks so let's lean in on that."
- DIGGER clip 02's thumbnail pinned at 194.5 s (the window shot with Sandra Hüller) via `thumb_t` in plan.json.
- Bot: `bot/models/genderage.onnx` (InsightFace buffalo_l attribute head, 1.3 MB, read with OpenCV's DNN, no new
  dependency) scores every candidate face; a clear woman's face gets up to 1.6x in the thumbnail picker, and the
  4-frame options sheet always includes one when the clip has one. RULES.md 20 updated.

## 2026-10-29 (03:20 UTC): thumbnails rebuilt after rico's verdict
- rico: "are you able to pull images or make the clips better as in clickbaity... the one you made is very creepy and
  no one would want to watch that, it's weird. also the text is bad."
- Outside images stay banned (the campaign briefs allow only the footage itself), so the fix is the choice of frame
  and the text. `bot/thumbnail.py` rewritten: the frame is the most clickable face, not the loudest one (frontal,
  sharp, mid-size, zoom at most 1.5x, not at a sound peak: the first version weighted "the payoff at the end" and
  picked Rockwell mid-scream at 1.8x zoom); text is 2-6 words in huge Montserrat Black with one yellow word, placed
  away from the face; light pop grade instead of a heavy black gradient. The reviewer can pin `thumb_text` and
  `thumb_t` per clip in plan.json. Every clip also gets a 4-frame OPTIONS sheet beside the thumbnail so rico can
  pick another frame by number. Approved clips get their thumbnail remade when the look or the pins change (the old
  cover frames are cut off first). RULES.md 20 rewritten. DIGGER pins: 01 "A $1 billion rig... over a crack?" at
  51.9 s, 02 "Is that all the bad news?" at 212.5 s (Tom Cruise, mouth shut, staring).

## 2026-10-29 (03:00 UTC): thumbnails for Shorts, TikTok and Reels
- rico: "what about thumbnail on YouTube Shorts. make sure it's really good."
- Bot: `bot/thumbnail.py` builds a 1080x1920 thumbnail from the episode's own frames (best reacting face, the hook in
  big white/yellow text) for every kept clip, uploads it beside the clip (1_CHECK and 3_APPROVED) and appends it as the
  clip's last two frames so the YouTube and TikTok frame pickers can select it (no custom thumbnail files on Shorts);
  Instagram takes the PNG. Clips approved before this got their thumbnail on the next run (DIGGER 01 and 02). The
  POST KIT says where the picture is and how to pick it. RULES.md 20 updated.

## 2026-10-29 (late): one platform per clip, by category
- rico: "I thought we were separating clips from campaigns on Insta, TikTok and YouTube based on the category of the clip."
- Rule: a clip is posted to ONE platform. YouTube (@fedsaa) = business / money. Instagram (@fesavoo) = celebrity /
  pop culture / drama / gossip. TikTok = entertainment (comedy, streamers, gaming, music, action, sports).
- Bot: `bot/lanes.py` scores each kept clip's own words on the 12 genres plus money and celebrity words; a movie,
  stream or concert starts from TikTok, a podcast from YouTube, and another lane must beat that clearly. When every
  clip of a campaign lands in one lane, the clip whose second lane is at least half as strong moves there (lane
  diversity). The SUMMARY in 1_CHECK shows "post on: …", `state.json` keeps it, the POST KIT lists only that platform.
  The reviewer can pin `"lane": "youtube"` on a clip in plan.json. DIGGER: clip 01 → TikTok, clip 02 → YouTube.
- rico chose "Keep in-house engine" on the OpusClip question: no outside reframing service.

## 2026-10-29 (02:00–02:45 UTC): DIGGER runs 7 and 8
- Run 7 kept 0 of 4: the gates rejected the Tom Cruise clip (centred 11%, faceless window shot) and the two clean
  clips scored 76 and 75, under the judge bar of 80.
- Bot: movies search faces at 1280x720 (`analyze_shots.faces_in/track hi=True`; an actor across the room is 20 px
  wide at 640 and was missed); mouth motion measured in the frames' own size; limiter at -3 dBFS (hot trailer music
  true-peaked above the audio gate); footage text touching an edge must be letter-sized; the judge's area breakdown is
  written into every TRY/KEPT/DROP line of data/last_run.log; when no clip of a run reaches 80, clips that pass
  **every** hard gate at 75–79 are uploaded marked "UNDER THE BAR" (rico decides; an empty folder helps nobody).
- Run 8 (02:33 UTC): 2 clips in 1_CHECK marked under the bar. rico approved both at 02:44 UTC, the first approval
  since the rebuild.

## 2026-10-29 (01:01 UTC): rico's run-6 verdict → full quality inspection
- rico: "still not centering correctly", "the transitions are ass", "the audio sounds weird", "the faces are not in
  frame", "some of the internal text in the show is cut off", "have a full quality rating and acceptance criteria",
  "heavy increase in judgement", "better scoring cards", "better rejecting meter", and asked about a secondary app.
- Bot (commit ea6a508):
  - YuNet neural face detector (`bot/models/face_detection_yunet_2023mar.onnx`, OpenCV DNN) replaces the Haar
    cascades in rendering and QA; HOG person detector as the faceless fallback.
  - The crop follows ONE identity per shot (`analyze_shots.track`): nearest to the chosen actor, a weak hit may only
    continue an identity, a hit more than 15% away is somebody else; when the speaker turns away the window keeps the
    other face inside it. Faces from 2.5% of the width count on movies. The dead zone is 6% of the WINDOW width (the
    old 8% of the source width was a third of a zoomed window). The glide between tracking keys never restarts
    mid-move (the old jerk).
  - Burned-in text steers the crop only when it is a real card (35%+ wide, or centred with nobody on screen); map
    labels on a globe, a video-call window, window grids and clock hands no longer count (`_text_rows` thin-bar rule).
  - Credit cards at a moment's edge are trimmed to their real end (brightness step, `card_end`); a fading tail under
    the first spoken word is covered with the picture after it (`video_swap`).
  - Movies: fixed gain + limiter (`plain_gain`) instead of loudnorm, which went dynamic on music ("weird audio").
  - Acceptance gates in `bot/qa_check.py`, listed in `scorecards/acceptance.md`: actors fill the frame, speaker
    centred (surest face in the upper 72%), somebody in frame (a movie's own scenery cut may run 3 s), footage text
    whole, crop jumps checked against the source's real cuts, one 9:16 look, audio loudness and range, captions,
    length. Judge bar 80 with a montage penalty and a title rule (number / question / quote / name).
  - OpusClip AI Producer offered as an A/B reframing engine (declined later the same night).

## 2026-10-28 (21:52 UTC): rico's run-4 verdict → grading and re-edit loop
- rico: "the screen is not focusing on actors", "the text font and shape isn't nice or good size", "the clips are
  fucking boring", "the screen keeps switching between 16:9 and 9:16 which is horrible and bad production", "have a
  bot grading the outcome of this clip and throw it back to re-edit or choose a better clip", "entertainment and
  amazing high tier quality is the most important".
- Rules: ONE 9:16 look per clip (the whole-frame "fit"/letterbox layouts are banned mid-clip, qa_check "One 9:16 look"
  FAILs them); the crop follows the actors and punches in up to 1.5x on wide shots; two-shots on movies are cropped on
  the talker, never split; wide credit cards at a moment's edges are trimmed (`trim_cards`); heavy Montserrat text
  for every profile (ExtraBold title, Black captions ~86 px, outline 8; Bebas Neue + Poppins were rejected).
- Grade-and-retry (supersedes the 10-27 "no re-cut loops", as long as it is bounded): under the bar → one re-edit
  (zoom boost, later opener), then the next best moment; max 3 renders per slot (`pipeline.try_until`, lanes with
  scorecard fallbacks behind the reviewer's picks). Bar 78 then, 80 since 10-29. Quality beats speed now, but a
  campaign still finishes in one run.

## 2026-10-28 (day): grading profiles, genres, speed
- rico: "a new scoring system for different media", "comedy grade", "different genres", "speed it up 20x".
- Bot: `bot/profiles.py` (podcast / cinematic / stream / performance: which QA checks are hard FAILs, pace and length
  targets); `bot/genres.py` (12 genres + comedy score; campaign mix from brief + transcript or plan.json
  `brief_overrides.genres`); judge 100 points (hook 20, pace 10, variety 15, framing 10, story 10, entertainment 10,
  comedy 5, captions 10, length 10); `bot/backtest.py` ranks approved clips against the scorecard. run.yml split into
  prepare → render (one machine per candidate, up to 4) → collect; faster render (face pass cached, ultrafast
  intermediates). Whisper medium for episodes under 25 min.

## 2026-10-27: the rebuild, lanes, no ads
- rico scrapped the PC system: private repo saarico/clipping-bot on GitHub Actions (cron every 5 h + hourly scan),
  Google Drive CLIPPING with 0_START / 1_CHECK / 2_REDO / 3_APPROVED, rclone token as a secret (rotate once stable).
- Lanes restated: YouTube = business/money, TikTok = entertainment/cool stuff, Instagram = girly / drama / celebrity;
  the campaign scorecard weighs success chance, entertainment value and lane diversity, not just pay.
- NO ad / brand / app-promo campaigns, no AI voice-over (after the FOLD clips: "horrible voice, blurry, not engaging").
  Goal: grow the channels with great entertaining clips of real content. Brand mode is parked.
- Max 3 clips per campaign; Mark Manson dropped for good; campaign requirements come from the MAIN campaign page and
  every post kit is re-verified against it; setup steps one at a time; no credentials in chat; never permanently
  delete a file (move to _trash); posting, joining and approving stay rico's clicks.

## 2026-10-26: the first review round (old system, rules carried over)
- "weird cuts and transitions", "horribly off centre", "b-roll is blocking his face", "no format switch", "empty room"
  on the wide two-shot, "lag at the start". Rules 21–26 in RULES.md (cut on the show's own camera cut, deflash,
  centred speaker with a dead zone, never a letterbox, never an empty room, no dead air, cards boxed at their
  biggest, the show's own footage only).
