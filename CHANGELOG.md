# Change log: every rule rico set and what changed in the bot

Newest first. Each entry: what rico said, the rule, and where it lives in the code. The living rule book is
RULES.md; the acceptance gates are scorecards/acceptance.md.

## 2026-10-30 (04:15 UTC): Higgsfield run 1 died of a full disk; fixed
- Run 40994897851 (03:00-03:54) stopped with "No space left on device" during prepare. rico's episode file is the 4K
  YouTube download; the 1080p conversion wrote at ~20 Mbit/s (ultrafast, crf 17): about 10 GB for an hour, on the
  runner's ~20 GB root disk next to the 1.2 GB original.
- Bot: the work folder is now /mnt/clipwork (the runner's second disk, ~60 GB free; env CLIP_WORK in run.yml, a "work
  disk" step in every job); conversion writes veryfast crf 21 (~4 Mbit/s) and deletes the original and the parts as it
  goes; the transcript wav is deleted after use.
- Bot: a single file in 0_START named like a yt-dlp download ("Title [videoid].mp4") whose id is in the brief's YouTube
  link is the same video: prepare takes the 1080p h264 copy from YouTube (3 min, YT_COOKIES) instead of converting 4K
  (most of an hour), and caches it on Drive for the render machines. The transcribe machines take the raw file as it is
  (audio only needs no conversion) and never write the cache.

## 2026-10-30 (03:30 UTC): the transcript on 4 machines, the episode download cached (rico: "15 min")
- rico: "one hour is a long time, can we increase speed to 15 min, have several agents take on the work and come
  together." Rendering already ran on 4 machines; the slow serial part of a FIRST run on a new episode was the
  transcript (a 1-hour podcast: 10-15 min on one machine) and, for a YouTube source, one download per machine.
- Bot: run.yml gets a `transcribe` matrix (4 machines, no dependency) that starts with prepare: each takes a quarter of
  the episode (`transcribe.py --part i/4`, 4 s of context each side, times in episode seconds, the model chosen from the
  whole length) -> artifact words-N. Prepare maps the graphics meanwhile, then `wait_for_parts()` pulls the 4 artifacts
  with gh (GH_TOKEN) and merges them (`transcribe.py --merge`); a missing or failed part = prepare transcribes itself
  as before. Campaigns with a transcript already in the repo skip all of this (the machines finish in a minute).
- Bot: an episode downloaded from a link (YouTube via YT_COOKIES, Drive, Dropbox) is now saved to Drive `_cache/<campaign>`
  like a converted one, so the transcribe, prepare and render machines of the same run download from Drive, and YouTube
  is asked once.
- Expected: first run on a new 1-hour episode ~20 min, later runs (redo, next clips) ~15 min. The floor is the machine
  set-up (~2 min per stage) plus the episode download on every machine (~2-3 min for 1 GB).

## 2026-10-30 (03:20 UTC): Higgsfield 20VC starts; watermark campaigns supported
- rico dropped the Higgsfield brief, the two watermark PNGs and the episode mp4 into 0_START (the YouTube file, so no
  download needed). The brief REQUIRES the Higgsfield watermark on the whole clip, big, readable, never covered; the
  bot had no watermark at all.
- Bot: `brief.watermark` (the word in the brief); `run.get_watermark()` takes the PNG from 0_START (named
  watermark/logo, else any PNG when the brief asks; the most opaque variant wins) to WORK/<campaign>/watermark.png on
  every machine; `pipeline.one_clip` hands it to render_clip as spec["watermark"]; render_clip overlays it 500 px wide
  at the top left of the picture (under the title band, above captions) for the whole clip and moves split-layout
  callouts under it. RULES 38.
- Bot: `brief.tags_by_platform` reads "YouTube: @HiggsfieldAI + @20VC / Instagram: @higgsfield.ai @20vchq"; the POST
  KIT puts only the platform's own handles on each post (before: all four on every post).
- The NEEDS THE VIDEO note and the JOIN doc no longer say "download it on your PC": a YouTube / Drive / Dropbox link
  in the requirements is enough, the bot downloads it (YT_COOKIES).
- Answered rico: downloads stay on the GitHub machine; only clips, SUMMARY, POST KIT and a converted-episode cache
  (_cache/<campaign>) reach Drive.

## 2026-10-30 (01:55 UTC): YouTube downloads from the cloud, no home PC
- rico: the home PC must have no part in the pipeline ("fully automated, fully online"; he travels). YouTube refuses
  GitHub machines without a signed-in session (probe 2026-10-27, again today).
- Bot: secret `YT_COOKIES` (cookies.txt of a THROWAWAY Google account, SETUP.md "YouTube episodes from the cloud")
  reaches prepare, render and probe; `run.yt_cookies()` passes it to yt-dlp (`-N 4`, retries); a refusal writes the
  note "YOUTUBE COOKIES NEEDED OR EXPIRED". probe.yml now downloads 20 s to prove format access ("DOWNLOAD OK").
  Drive, Dropbox and direct links keep working with nothing extra.
- 02:12: VERIFIED. rico set the secret (Firefox "cookies.txt" add-on); probe run 40990280804 downloaded 1080p from a
  GitHub machine ("DOWNLOAD OK"). Cookies alone were not enough: YouTube now serves only signed formats, so
  requirements.txt installs `yt-dlp[default]` (the EJS challenge solver) and yt-dlp runs with `--js-runtimes node`;
  h264 1080p first, remuxed to mp4. A YouTube watch link in the requirements doc is now a valid episode source.

## 2026-10-30 (00:45 UTC): TJR skipped, the board re-read, dedicated-account campaigns stopped
- rico: "let's skip, it's likely we wouldn't be accepted. Scan for something else and delete this campaign on Drive."
  TJR's folders went to _trash (config/dropped.txt). Lesson: Reach campaigns want the posting account's niche to
  match or a dedicated account; rico's channels are general.
- Bot: `campaign_scan` stops "dedicated account / fan page / Reach" campaigns (unless the card says "no fan page
  needed"); KNOWN_SHOWS settles the lane for shows whose title hides it (Iced Coffee Hour = YouTube money, BILF =
  Instagram, Kai Cenat = TikTok). pages.yml survives a concurrent commit; summary.json accumulates.
- Board 00:20 UTC (73 cards, descriptions read, 6 unknown person campaigns' pages read): only three real podcast
  campaigns remain: Iced Coffee Hour x Greg Lav (recommended, folder made), BILF Podcast (8 days of budget),
  Higgsfield 20VC. Decision card to rico.
- 00:44: rico: "I already did [Iced Coffee Hour]. Consider something else, including the ones we scanned and rejected,
  and choose by your scorecard." Rule from now on: the bot picks the campaign (top card that passes every stop) and
  tells rico; no decision cards for picks. Picked Higgsfield 20VC (71, YouTube business lane); runner-up BILF (89)
  blocked by ~8 days of budget. ICH x Greg Lav withdrawn.

## 2026-10-29 (15:25 UTC): the scan reads campaign pages, "close to ending" by pay-out pace
- rico: "scan for a campaign, ensure proper rules and best choice and ensure the campaign isn't close to ending."
- Finding: Content Rewards campaigns have no end date (pages rendered with a browser on the runner: description,
  launched-ago, rates, budget spent/total, clipper count; rules and files "visible once you join"). A campaign ends
  when its budget is spent.
- Bot: `bot/campaign_pages.py` + `.github/workflows/pages.yml` (manual: ids or links) save each page's text and
  data under data/campaign_pages/. `campaign_scan.auto_score` adds `days_est` = budget left / pay-out per day since
  launch; under 10 days is a stop unless the title says weekly/monthly. Brand content banks ("content bank",
  "trading cards", "collectibles", "merch") count as ads: the hourly scan had offered Topps x Clipfarm at 13:21.
- Offered: TJR $23,100 Weekly (Reach; streamer, lane C) with a JOIN doc in 0_START; decision card to rico with
  TJR / It's Personal / Topps / keep scanning. RULES.md 36 extended.
- 16:20-16:35: rico joined TJR; Topps withdrawn (config/dropped.txt). Rules read from reachclipping.com/TJR and pinned in
  campaigns/TJR .../plan.json (stream profile, #TJR, 10-60 s, account niche rule). Bug: run.yml inlined the campaign
  name in the shell, so the "$" in "TJR $23,100 ..." was expanded and the run matched no campaign; the name now goes
  through an env variable. First TJR run read the brief (8 rules); waiting for rico's episode.mp4.

## 2026-10-29 (05:10 UTC): code audit round 2, 21 fixes
- rico: "audit the code fully for improvements, bugs, updates and fixes." Round 1 (10 findings, pitch/judge shared
  scorers, brief lengths, look validation) landed at 04:45. Round 2 read every file under bot/.
- Fixed, would have bitten the next campaign:
  - POST KIT: approving a second clip rewrote the doc with only the new clip; the kit is now written for every
    approved clip whenever one is new or a thumbnail changed (`run.py` approved block).
  - Thumbnails never reached 1_CHECK on the parallel pipeline: the render machine rewrote the clip's path but not
    the thumbnail's, so collect uploaded clips without PNG or options sheet (`render_job` / `collect`).
  - A single episode file that is not 1920x1080 (720p, 4K, letterboxed) stopped every render with SystemExit; it
    is now converted like a joined episode and cached on Drive (`get_source`).
  - A step that ran out of time (render 40 min, QA 30 min) raised through the whole machine; it now returns a
    failed result and the next try runs (`pipeline.sh`).
  - rclone errors (expired token, quota) read as "folder empty" and the run did nothing, silently; now they raise
    (`drive.Rclone.ls`; a missing folder is still an empty list).
  - A remade thumbnail could stack a second cover frame on the first; the old cover is always cut (`ensure_thumbnail`).
  - A reviewer's genre list in plan.json crashed judge_clip (`mix.items()` on a list); normalised in plan and judge.
  - The judge graded length against the profile alone; the brief's min/max now travel in the spec (`plan.brief_lengths`).
  - render_clip.snap on a part with no words inside built an inverted search range; the part is left as is.
  - Scan: a card with `views: null` crashed the score and vanished; crypto / web3 / "teasers" promos are ads.
- Fixed, cost or hygiene:
  - Nothing kept three runs in a row: the campaign waits for a note in 2_REDO or a plan.json instead of rendering
    the same episode every 5 hours (`empty_runs`); moments rendered and dropped go to `tried_moments` so the
    scorecard moves on; `used_moments` keeps one entry per moment.
  - Old thumbnail PNGs / options sheets in 1_CHECK go to _trash with the old clips.
  - The best failed try is ranked QA-pass first, then judge (a "near" clip beats a higher-scoring QA failure).
  - The scan ran inside the main run and in its own hourly workflow; two commits raced on scan_seen.json. Hourly only.
  - 720p face search decodes 6 frames instead of the whole stretch at 10 fps; the gender net is skipped while
    `WOMAN_BOOST = 0`; the scorecard writes hooks only for windows that reach the pick loop (3.6 s for DIGGER);
    `drive.root()` checks the stage folders once per process.
  - Dead code removed: the scan's unused page-enrichment loop and `card_from_page`, qa_check's post-text/tags.json
    check (no file ever existed; it could never pass), a duplicate lane set in the scan.
- RULES.md 37 added. Checked locally: pitch on DIGGER (89/82/74 PASS unchanged), judge on clip_c01 (80/100
  unchanged), the scan's cards re-scored offline (only It's Personal = JOIN), the new helpers in isolation.

## 2026-10-29 (04:30 UTC): accounts, the pitch gate, campaign looks, MW4 withdrawn
- rico: "where would these clips go, what site and why; why Call of Duty, isn't it supposed to be more girly; it leans
  heavily on ad; categorize my accounts and judge campaigns better; tailor the editing to each campaign's style;
  have the bot read the script and decide if it's entertaining enough before making clips; audit the code."
- MW4 Campaign Moments withdrawn (config/dropped.txt; a game-launch promo). It's Personal Podcast stays offered
  as the Instagram candidate.
- Bot: `config/accounts.json` identities + RULES.md "Accounts" table; `campaign_scan.py` rejects campaigns that fit
  no account and game footage with no person in it (`game_promo`), and the JOIN doc names the account.
- Bot: `bot/pitch.py`, the pre-render judge (RULES 34): every candidate's words are graded on the campaign's
  profile and genres; under 60 it is not rendered; SUMMARY lists every pitch. DIGGER's three reviewer picks pitch
  83 / 82 / 74 on the current words.
- Bot: per-campaign look (RULES 35): `brief_overrides.look` in plan.json overrides accent colour, caption size,
  words per caption, title size, outline, shadow; `profiles.look(name, overrides)`; the SUMMARY shows style and look.
- Parallel workers already exist since 2026-10-28 (one render machine per candidate, up to 4); unchanged.
- Code audit requested; see the next entry.

## 2026-10-29 (04:00 UTC): the gender detector was wrong, automatic "women first" switched off
- rico: "THAT'S NOT A FEMALE ... AUDIT AND CHECK AGAIN AND NEXT TIME FULLY CONFIRM." The bot had told him the
  clip 02 option 4 frame (194.5 s, the long-haired person at the window) was a woman, on the strength of the gender
  model. An audit of all 386 faces in the DIGGER footage: the model also called two cats, the man in the parka and
  the old man on oxygen "women" with high margins. Unusable on this footage.
- Bot: `thumbnail.WOMAN_BOOST = 0` (the preference and the "one woman on the options sheet" rule are off; the
  margin is still measured). "Women first" is applied by the reviewer by eye through `thumb_t`, and only after
  rico confirms the frame. RULES.md 20 updated. Clip 02 keeps the frame rico chose (option 4) unless he says otherwise.

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
