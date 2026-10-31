# Change log: every rule rico set and what changed in the bot

Newest first. Each entry: what rico said, the rule, and where it lives in the code. The living rule book is
RULES.md; the acceptance gates are scorecards/acceptance.md.

## 2026-10-31 17:45 UTC - Studio v2 release 3: inspection v2 (version 2.3.0)

First-piece preview (first 20 s of the top 3 moments rendered small in prepare; failures go to the back of the
queue), contract checks on every agent hand-off, last-piece inspection (flash ending, silent tail). Broken hand-offs
and a bad ending fail QA; everything else is a note. inspection.md per clip, an inspection line per clip in the
SUMMARY. Golden set unchanged (the judge is untouched). RULES 48.

## 2026-10-31 17:35 UTC - Studio v2 release 2: the render is six agents (version 2.2.0)

rico approved all 4 releases of the Studio v2 plan (17:19). render_clip.main's 240 lines are now bot/agents/
(editor, camera, sound, graphics, captions, finisher), each handing the next a contract kept as <name>.agents.json /
agents.json. No output change: two test specs (podcast with teaser, card, callout, watermark, end hold; cinematic)
rendered identically before and after (framemd5 of every video frame and audio packet). New test: tests/test_agents.py.
RULES 47.

## 2026-10-31 16:55 UTC - Drive folder downloads broke on gdown 6

gdown 6.x removed the `--fuzzy` flag (URLs are parsed by default), so every Drive link in a brief failed with
"unrecognized arguments" and the bot asked rico for the file (DJ Drama run 41221080177, 16:47). run.fetch_link now
calls `gdown --quiet -O <dir>/ [--folder] <url>`. No rule change.

## 2026-10-31 (15:50 UTC): QA and layout after Malcolm Todd run 41213092925 (1 kept of 4 rendered)
- c04 failed "Faces clear of the title" (face under the hook text): render_clip records where the top of the face
  lands in the finished picture during the hook seconds (spec._face_top); when it would sit under the hook + who-line,
  the block goes to the bottom just above the captions (\an2, bottom edge at CAP_DEFAULT - 90) for its 5 seconds and
  number cards wait until it fades. qa_check reads the zone from \an8 or \an2 and flags a face inside it.
- c03 failed "Picture (frozen at 14.3s, 17.9s)" on a locked-off interview shot: freezedetect noise is 0.003 for
  talking profiles (cards=True) and stays 0.001 for movies/streams, in both the whole-clip and first-2-seconds checks.
- The Spotlight interview is filmed from across the room (faces 4-7% of the picture): the wide two-shot punch-in cap
  goes 1.35x -> 1.6x on talking shows (beyond that the 1080p picture goes soft); pipeline.faces_ok keeps its 7.5% floor.
- Branch claude/qa-layout-fixes, PR #2, after the studio PR #1 (480165d).

## 2026-10-31 (17:20 UTC): Studio v2 release 1, the safety net (version 2.1.0)
- rico 17:19 UTC: "release all 4" (board review 2, Studio_v2_Engineering_Plan_2026-10-31.pptx). Releases ship in order.
- tests/: 18 gate tests, golden set of 4 approved ICH clips (baseline judge 78, 79, 73, 68), DIGGER replay (approved
  moments rank 2-3). CI: .github/workflows/test.yml (pull requests only; ruff E9/F63/F7/F82 + pytest).
- pipeline.report_card -> data/report_card.csv after every collect; studio.VERSION in the SUMMARY.
- No change to what the bot cuts or keeps.

## 2026-10-31 (15:40 UTC): the clip studio, board decisions 1-3
- rico 15:31 UTC: "approve 1 - 3" on the board deck (Clip_Studio_Board_Review_2026-10-31.pptx): the studio design,
  the campaign filter, a higher cap on proven campaigns. Decision 4 (a $0-60/month tool budget) was not approved.
- bot/studio.py (new): ROSTER of 15 roles and INSPECTION_LINE of 9 checkpoints mapped to the modules that do them;
  weighted_total, layout_check (Text & layout inspector), speaker_check, clip_cap. `python3 bot/studio.py` prints both.
- bot/profiles.py: talker, serious and edit profiles (same keys as the others), LOOK for each, TEXT_HINTS; WEIGHTS per
  profile (sum 100) and AREA_MIN (10, 0.5). bot/lanes.py baseline for the new profiles.
- bot/judge_clip.py: a sound area (qa Audio row); every area measured on its own scale and weighted per profile; under
  half on a 10+ area or a layout failure holds the clip at 79. judge_report.md has Measured / Weight / Points columns;
  bot/pipeline.py reads the new table and a layout failure is never "near" (no UNDER THE BAR upload).
- bot/find_moments.py: opener_ok refuses filler/reaction starts (a host question starting "So..." still opens), lines
  over a quarter fillers and lines ending on a dangling word; hook_from_opener cuts a long title at a clause (Malcolm
  Todd run 41213092925 titled a clip "Oh yeah, but he does this wrong, and he does like, now.").
- bot/campaign_scan.py: RISKY stop (gambling, crypto, tokens) and pay under $0.50 stop.
- bot/pipeline.py: speaker check note in every SUMMARY; decide(cap=). bot/run.py: collect passes studio.clip_cap(state),
  the render matrix gets one machine over the cap.
- Checked offline: weights sum to 100 for all 7 profiles; the judge re-scored ICH-001/004 (pre-rule-42 title band:
  layout FAIL as expected); Malcolm Todd pitch reproduced (24 pitched, 7 passed, no dangling titles).

## 2026-10-31 (09:55 UTC): the transcribe machines convert a multi-file episode side by side
- Run 41179325133 (07:42-09:43) rebuilt the 5-interview episode on the prepare machine alone: 2 of 5 parts converted
  (18 and 38 min) when the 120-minute job limit of its workflow version cut it off. Nothing was lost: both parts are in
  the Drive part cache.
- run.convert_part (one file -> 1080p30) is factored out of join_videos. A transcribe machine that finds no joined
  episode for a multi-file campaign converts its share (run.parts_for_machine: biggest files first, each to the machine
  with the least so far) into _cache/<campaign>/parts and uploads it; prepare waits up to 110 min for the parts to
  appear, joins them (concat copy), and only converts itself what is still missing. Five interviews now take about
  one hour instead of four. transcribe job timeout 90 -> 150 min.
- Then the usual follow-up: a fresh long episode is cached and the follow-up run (actions: write, in the workflow
  since 07:20) transcribes it on 4 machines and cuts.

## 2026-10-31 (08:30 UTC): the picker after Malcolm Todd's first cut (0 clips kept of 6 pitches)
- Run 41172674913 (07:05-07:42, the 4-interview episode): 6 moments pitched, all 6 failed the audience gates ("the
  headline is not said in the first 6 s", "title has no name"), the best was rendered anyway and dropped by QA: no face
  for 30 of its 50 s, a face 8% tall in the rest, frozen opening frames. The brief's own subjects (Earrings, the
  sold-out tour, going viral) were never in the pool.
- Why: (1) the title was the window's strongest sentence, wherever it sat, so the gate "said in the first 6 s" could
  only pass by luck; (2) the brief's CONTENT IDEAS are bullet topics, not quoted hooks with times, so brief.clip_ideas
  found nothing; (3) only 6 moments were pitched (the render budget) out of a 3-hour episode; (4) whisper returned two
  of the four interviews with no punctuation, so one hour was 38 "sentences" of 93 words and had no window under 60 s;
  (5) nothing looked at the picture before rendering.
- Fixes: brief.topics (subjects from the idea sections, quoted titles double) feed find_moments.score_window ("brief"
  up to 15) and lead the candidate pool (the best window that OPENS on each subject, score 60+); talking shows only
  open on a hook line (find_moments.opener_ok) and the title IS that line (hook_from_opener); plan.PITCH_POOL 24 pitched,
  pitch.gate hands on up to 12; pipeline.faces_ok looks at five 2-second stretches at 720p and drops a moment without a
  face 7.5%+ tall in 3 of 5 (prepare only, where the episode is); find_moments.sentences breaks unpunctuated runs at the
  widest pause after 18 words and at 30 words regardless; transcribe.py gives whisper a punctuated initial_prompt.
- Offline check on the committed transcript (scratch harness): the pool now holds the tour (6-8 min), Earrings (157 min),
  virality vs a real career (93 min), "never went searching for success" (168 min); 9 of 24 pitches pass.

## 2026-10-31 (07:20 UTC): every file in 0_START is used; parts cached; transcript tied to the episode (Malcolm Todd runs 2-3)
- Run 2 (05:10-07:05): rico's 5 interviews were in 0_START; the bot skipped "Malcolm Todd on Ice Cream Dreams, TikTok
  Fame ... | Office Of" because its skip rule read "tiktok" in the name as a vertical cut, then converted the other 4
  (3.2 h) for 1 h 50 and hit the 120-minute job limit before transcribing; the episode did reach the cache. Run 3 cuts
  from that cache.
- run.VERTICAL_NAME is now only vertical / igtv / 9x16 / 9_16 / portrait (join_videos drops real portrait files by their
  size anyway); pick_files + source_sig give one answer to "which files make the episode" for prepare and the transcribe
  machines; JOIN_VERSION in the signature rebuilds caches made by the old selection.
- Drive part cache _cache/<campaign>/parts/<md5(name:size)>.mp4: each converted part is kept, so adding one interview
  converts one file (join_videos ready= / saved=).
- state.source {sig, files} + state.words_sig: a transcript is valid only for the episode it was made from; the
  transcribe machines redo it otherwise, and used/tried moments are cleared when the file order changes (kept when
  files were only appended). A transcript without words_sig (from before today) is redone once.
- A long episode (over 40 min) built in this run no longer gets transcribed by the prepare machine alone: prepare
  caches it, dispatches a follow-up run (gh workflow run; run.yml actions: write) and ends; the follow-up's 4 machines
  transcribe from the cache. prepare timeout 120 -> 300 min as a safety net.
- Policy unchanged: with 3 clips waiting in 1_CHECK the bot does not touch the episode; the 5th interview joins at the
  next cut (a redo note, or fewer than 3 clips kept).

## 2026-10-31 (04:05 UTC): rule 43, episodes by PowerShell; Malcolm Todd run 1 blocked on YouTube
- Run 41165260381 (03:40): brief read (7 rules, 5 links, TikTok + Instagram only), all 5 YouTube links refused
  ("Sign in to confirm you're not a bot"): the YT_COOKIES cookies expired again. rico: "can you just download on
  PowerShell or GitHub" -> "no, let's just continue with PowerShell; consistent correct paste format and no errors;
  ensure all videos get downloaded when provided; ensure the md knows this".
- RULES 43 + SETUP.md "Episodes by PowerShell": one yt-dlp command (all links, -P Downloads, --windows-filenames,
  1080p h264), drag into 0_START; the bot joins every file (run.get_source / join_videos, unchanged). The first
  command sent wrote into C:\Windows\system32 (admin PowerShell) and failed with Permission denied; -P fixes it.
- brief.parse: platforms are read from the rules text with URLs removed (the YouTube asset links had added "youtube"
  to a TikTok + Instagram brief); the Malcolm Todd state was patched before collect.
- Options declined for now: residential proxy (YT_PROXY, pay per GB), yt-dlp token plugin test.

## 2026-10-31 (03:35 UTC): next campaign picked: Rolling Stone & Malcolm Todd Interviews (Instagram lane)
- Board of 64 cards (scan 41164326405): every card over 55 is a game-launch ad, a brand ad, Mark Manson or a
  dedicated-account campaign. The campaign pages themselves are readable from the sandbox (pay per platform, budget,
  description; rules hidden until joined), so the real-content "?" lane cards were checked by hand: Rolling Stone &
  Malcolm Todd Interviews (creatorXchange, $2/1K TikTok + Instagram, max $200, $2,336 left, 112 clippers) is a real
  interview and fits the Instagram celebrity lane; picked, 0_START folder + JOIN doc made. Runner-up Parrot (Shark Tank
  episode): $1.50/1K on all three, $5k untouched, 0 clippers, real show footage but the company's own pitch = brand
  rule; told rico, not joined. Skipped: Michael Sartain (a mentoring business, rules hidden), Sabri Malle (Spanish,
  dedicated-account style), Backyard Breaks and Up Next Fighting (dedicated/niche accounts), Open Road (app), Mad Honey
  ($884 left), DJ Drama Business of HipHop ($0.75 floor, $1.8k, 0 clippers; clean lane-A fallback), Reuben A Geimah and
  Jackelyne (no description at all).
- Scan lesson: the "fits none of the three accounts" stop hides interview/music/documentary shows whose title has no
  lane word; the campaign page's description is fetchable and should feed content_fit.

## 2026-10-31 (03:30 UTC): Higgsfield killed by rico
- rico (03:25): "trash this campaign, the guy is just horrible at speaking and so bad at communicating, hard to listen
  to. Scan for another campaign. Remove the files, wipe clean each inner folder. I will leave the campaign."
- Every Higgsfield folder and file in 0_START, 1_CHECK, 2_REDO, 3_APPROVED, _cache and the bot's _trash went to the
  Drive trash (recoverable for 30 days, nothing permanently deleted). The campaign is in config/dropped.txt; its state
  is gone from the repo; its critique files (the source of rules 39-42) live on in docs/critiques/higgsfield-20vc.
- Lesson for the scorecard: a guest who speaks haltingly kills a campaign however good the numbers are. The pitch's
  clarity read (restarts + fillers) saw it clip by clip; the campaign scan cannot hear the speaker before joining.

## 2026-10-31 (03:05 UTC): run 13 under rule 42: 2 clips in 1_CHECK
- Run 41161111496 (02:42-02:59): "Top creatives could spend $100,000 a month on AI" (50 s, judge 89, audience 83) and
  "We spend $4M a month on AI for 400 people" (35 s, judge 85, audience 92) passed every check with the new look
  (framing 10 on both; run 12's "Somebody in frame" failures are gone). "Open models" dropped again on a stray cut at
  0.13 s, "90 minutes of film" on a clipped word at its start; "I thought AI would replace legal and support" did not
  get a render lane this time (4 lanes, 6 pitches). Both clips YouTube @fedsaa.
- captions.txt (build_clip_folder) no longer lists the who-line as spoken words (it was prefixed to the first caption
  line in the SUMMARY, which the judge reads).

## 2026-10-31 (02:45 UTC): run 12 rendered 0 clips: the QA face-size line, not the look
- Run 41159114829 (02:15-02:37): all 4 renders failed "Somebody in frame | no face for ..." on the stretches where the
  show is on its wide two-shot. Under rule 42 that shot is no longer split but cropped on the talker and punched in
  1.35x, which leaves the face ~19% of the picture width; the QA line for talking shows demanded 25% (a close-up is
  ~38%). The line is now 15% (bot/qa_check.py, "Somebody in frame"); it still catches an empty room. The sharpness is
  the same as the old split's panels (both upscale the wide shot about 2.1-2.4x). Same 3 moments re-rendered = run 13.

## 2026-10-31 (02:15 UTC): no title band, one caption spot, a who-line (rule 42)
- rico (02:02, on run 11's clips): "kinda close but you're still losing me on what. What are we talking about, who is this
  guy, what is the topic, when where why, why does it matter. Also the text captions are not consistent, very hard to
  track, sometimes above, other bottom, other center. Keep it nice and nice to look at. Also do we need to have an above
  header? Is that required by the campaign? Because it looks ugly."
- The brief checked: the hook is required "on top, shows the first few seconds of the clip, like a spoiler" and the
  on-screen text rule says "your own hook onscreen (first few seconds of clip)". A permanent header is NOT required.
- bot/render_clip.py: TOP = 0 (the footage fills the whole 9:16 frame, no band, no pad); the hook is a timed overlay
  under the watermark for the first 5 s with an outline and a fade (HOOK_SECS, HOOK_MAX 76 px); a who-line under it in
  the accent colour (style Tag, 40 px shrinking to fit); captions at one fixed y (CAP_DEFAULT 1400) for the whole clip,
  number cards at one fixed y (CALLOUT_Y 1150); the watermark in the top left corner (36, 36). Talking shows never
  split the picture: a two-shot is cropped on whoever talks (the 720p face pass gives the mouth motion), punched in up
  to 1.35x when the faces are small. Run 11's captions jumped because the stacked split put them on the seam and the
  "center"/"side" layouts had their own spots.
- bot/brief.py speaker_tag(): reads "X built Y, an ... company" + the full name elsewhere in the brief -> "Alex Mashrabov
  · built Higgsfield (AI video)"; plan.spec_for passes it as spec["tag"]; a campaign's state may carry its own
  "speaker_tag" (Higgsfield: "Alex Mashrabov · Founder of Higgsfield AI").
- bot/qa_check.py: TOP = 0; "Faces clear of the title" now flags a face under the hook text in the first seconds.
  brand_mode (parked) keeps its own 240 px band.
- RULES 42, Story structure beat 5 rewritten (hook + who-line, no band), rules 18 and 38 reworded; acceptance.md.
- Higgsfield: the same 3 moments re-rendered with the new look (used_moments cleared, needs_redo) = run 12.

## 2026-10-31 (02:05 UTC): run 11 under the story format: 3 clips in 1_CHECK; lanes obey the brief's platforms
- Run 41155818876 (01:36-01:55): "Top creatives could spend $100,000 a month on AI" (50 s, judge 89, audience 83,
  opens on Harry's question), "We spend $4M a month on AI for 400 people" (35 s, judge 84, audience 88, opens on the
  $10,000-a-month line, ends on "$10,000 per person"), "I thought AI would replace legal and support. I was wrong."
  (37 s, judge 84, audience 91). 7 of 12 pitches passed; "Open models" and "30% churn" dropped at the cut (stray cut,
  clipped word).
- The lane picker moved the third clip to TikTok for lane diversity although the brief allows YouTube Shorts and
  Instagram Reels only. lanes.assign now takes the campaign's platforms and never leaves them (pipeline.decide and the
  post-kit path pass them); the clip's lane in state is corrected to YouTube.

## 2026-10-31 (01:40 UTC): rico on run 10: "poor ending on the 1st clip, confusing; both clips yap for the first few seconds; the storyline, 5 Ws, progression and hook are weak; revamp the md files"
- The $4M clip opened on "And remember like we're split across United States and Asia" and ended on "That's the best
  question of the whole show, by the way"; the $20 clip opened on "But fundamentally, I think they are going to..."
  with the $20 said 6 s in. Both passed the read because the hook line and the payoff were points, not gates.
- Story format rewritten (RULES: Story structure section, rule 41; scorecards/acceptance.md, judgment.md) and made
  hard gates in bot/engage.py: the headline is SAID in the first 6 s (a money figure or big number, the title's name,
  or the host's short question naming the subject); a subject named or 30% of the title's words in the first 10 s (the
  viewer never depends on the title band); new stakes after the hook (progression); the last line lands a stake or the
  title's claim. Areas now: open 25, story 20, payoff 20, retention 20, clarity 15. The read takes the title; the
  pitch, the edge search (plan.refine, now 3 sentences earlier to 6 later) and the finished-clip pass all use it. The
  flat-stretch gate needs three dead windows in a row (two cost points).
- Higgsfield: tried/used moments cleared so the brief's ideas are cut again under the story format; redo set.

## 2026-10-31 (00:45 UTC): run 10: 2 clips above every bar in 1_CHECK
- Run 41149166104 (00:25-00:39, 14 min): "We spend $4M a month on AI for 400 people" (31 s, judge 88, audience 92,
  three number cards) and "Google and OpenAI will kill the $20 AI plans" (41 s, judge 83, audience 96). Both
  YouTube @fedsaa. "My mom worked three jobs" ended on "did sacrifice" (dropped), "One full day with my son" judged 72.
- The $4M clip ends on Harry's "How has that changed over time? That's the best question of the whole show, by the
  way." A compliment on a question is not an answer: bad_end now also fails a last line with "by the way" or
  "great/good/best question" anywhere in it (applies from the next run; the clip stays for rico's verdict).
- Moments dropped for a render glitch (a stray cut, a clipped edge) sit in tried_moments like content rejects; the
  brief's "Top creatives $100k", "Open models 80% margins" and "Investors shook hands" are blocked by that for now.

## 2026-10-31 (00:25 UTC): run 9 kept 1 of 4 (judge 79); cut edges and thin fallbacks fixed
- Run 41146816827 (23:52-00:11): the $4M clip with its number cards reached judge 79 (variety 7/15: one 14 s
  stretch without a visual change). Three dropped at the cut edges: whisper's sentence breaks with no pause
  ("...the same Did you know", "...insider Like") left a clipped word at the start and the end; the Yuri clip also
  ended on the one-word "Like". A lane had no second moment to fall back on (5 pitches passed for 4 lanes).
- plan.refine now needs a pause at both edges (no gap = the window is avoided); the judge gives talking shows a
  longer stretch between visual changes (15 s, their camera is still by rule); up to 4 number cards per clip;
  pitch.gate hands the best near-misses (no audience gate failed, 50+) to the lanes as marked fallbacks.

## 2026-10-30 (23:55 UTC): first run with the audience read: 2 clips, both under the judge's bar
- Run 41143673790 (23:19-23:43): 18 brief ideas read, 8 of 12 pitches passed, 2 kept under the bar (judge 76: the
  still camera left "variety" at 4/15 because punch-ins and b-roll were counted), 2 dropped for a stray cut (the
  show's own camera change inside the first 1.5 s; the re-edit re-rendered identically).
- Editing (rico: "bump up editing"): every dollar figure or number a talking show says becomes a big number card
  ("$10,000 A MONTH", "4 MILLION", "30% LOWER"; plan.auto_callouts, at most 3 per clip, 6 s apart). The judge takes
  no points off for a still camera on talking shows (RULES 39). The re-edit moves a cut edge past a stray cut.
- Grading: the Yuri clip opened on "This industry still gonna be very valuable..." (the tail of the previous answer)
  and ended on Harry's next lead-in "You're at a billion in revenue now." and passed the read. Now: a pointer start
  with no number, name or question is a gate; a host lead-in ending ("you're...", "tell me", "let's", "I want to") is
  a gate; sentences split on whisper's own capital letter ("...be the same Did you know..."); family and hardship
  words count as something to hold on to (the "My mom worked three jobs" idea passes). A brief hook that swallowed
  the table's note column is cut at the seam ("30% churn in month one.").

## 2026-10-30 (23:30 UTC): rico on the kept Higgsfield clip: cuts out in a horrible position, hard to understand, boring
- rico: "why is the clip cutting out in a horrible position, also he can't talk and it seems so uninteresting and
  boring and hard to understand; bump up editing, improve grading quality and entertainment, maybe add a second phase
  of engagement scoring." The clip opened on Harry's "I do just want to go back to part of the story" and ended on
  "By the way your co-host Jason also asked this question in May" with the question "How do you calculate revenue?"
  unanswered; judge 83, every gate green.
- New second grading pass, the audience read (bot/engage.py, RULES 40, scorecards/acceptance.md): cold open, clarity,
  payoff, retention, focus; four hard gates. On the Higgsfield brief's 20 usable ideas it passes 10 and rejects 10
  (hanging questions, flat stretches, 12 fillers in 117 words); the clip rico saw scores 62 and fails two gates.
- The read now chooses the cut's edges (plan.refine: the sentence window with the best read, within the brief's
  length), rejects moments before rendering (pitch.score) and grades the finished clip (engage_report.md; the re-edit
  moves the cut to the read's start and end). SUMMARY and state carry the audience score next to the judge's.

## 2026-10-30 (23:10 UTC): Higgsfield re-cut run kept 1 of 4; three bot defects fixed
- Run 41137471939 (22:20-22:45): the brief reader found only 3 of the brief's clip ideas, because the PDF table
  wraps the hook column (the quote opens on the line above the time and closes on the line below). brief.clip_ideas
  now reads every layout the table comes out as: 23 ideas from the Higgsfield brief (was 3). Two-part ideas marked
  "+" and ranges under 15 s are skipped.
- The re-edit re-rendered a clip identically when the failure was a clipped word at a cut or an unfinished last
  sentence (c02 "$4 million" failed twice the same way). pipeline.reedit now moves the start to the next sentence
  start and the end back to the last finished sentence inside the brief's length window.
- The centring gate measured talking shows against the movie line (12% off centre per frame) while the still camera
  lets a face sit up to 10% off by design (c01 dropped at 18%). qa_check.check_centred uses 17% on talking shows,
  12% on movies. RULES 39.
- Higgsfield: the "$4 million" try is cleared from tried_moments so the brief's first idea gets its re-edit; redo set.

## 2026-10-30 (21:20 UTC): rico on the Higgsfield clips: camera moves too much, boring opener
- rico: "the clips seem to be moving too much because of the clipping on the face, very distracting"; "can we ensure
  better content or is this the best it can do? I lost interest within the first 4 seconds."
- Camera (render_clip.pan_keys): talking shows lock the crop on the shot's median face position; it re-frames only
  after the face has stayed >10% of the width away for a full second, then glides 1.2 s (was: 4% dead zone, 0.5 s
  glide, re-centring on every lean). Movies/streams keep their fast follow (DIGGER, approved).
- Content: brief.clip_ideas() reads the brief's own "hook + time range" lines (Higgsfield lists 20); plan.brief_specs
  cuts them first with the brief's line as the title, after checking the words really sit at that time in our file
  (10 of 11 matched; "$1M and bought homes" is paraphrased in the audio and skipped). Scorecard picks follow. No clip
  opens on a filler sentence (plan.FILLER_START). RULES 39. Both Higgsfield clips in 1_CHECK are replaced by the
  next run (their moments stay in used_moments).

## 2026-10-30 (06:35 UTC): Higgsfield run 4: 2 clips in 17 min on the 4-machine path
- Run 41012562356 (06:10-06:27): transcript quarters on 4 machines (8-9 min each incl. the 4K download), prepare took
  them (merged 06:20), 4 renders of 3.3 min, collect. 2 kept (judge 84 and 83), 1 dropped for a clipped word at the
  cut, 1 under the bar. First run of a new episode = ~17 min; a redo = ~15 min.
- Bot: a title never ends in ",." (hook_text strips trailing commas/dashes before the final stop).
- YouTube: the probe at 06:11 got "Sign in to confirm you're not a bot" with the cookies that worked at 02:12: the
  session rotated (the throwaway account stayed signed in in Firefox). Export from a private window next time
  (SETUP.md), then close that window.
## 2026-10-30 (06:20 UTC): run 3: the 4 transcript parts were made but prepare could not read them
- Run 41001130950: the 4 transcribe machines finished their quarters in 6-10 min each (download of the 4K file
  included), but prepare's `gh run download` got 403 for 50 min: the workflow token had `contents: write` only.
  Prepare then converted the 4K file for 53 min (YouTube refused the cookies within 2 s, see the probe), cached it
  (properly, with its size), and was cut off by the 120-min job timeout while transcribing itself.
- Bot: `permissions: actions: read` in run.yml; a 403 or auth error on the first artifact read gives up at once (prepare
  transcribes itself) instead of waiting 50 min, and the first failure's error is logged. Handles and per-platform tags
  are read from the requirements file only, never from fetched pages (run 3 picked up 4 strangers' handles from a
  Discord/Drive page); Drive folders, WeTransfer, Dropbox and Discord links are not fetched as rules pages.
- Note: on the current ubuntu-latest image /mnt is the root disk (15 GB free), not a second disk; the lighter
  conversion (~2 GB) fits.

## 2026-10-30 (04:25 UTC): run 2 found a broken cache and a brief with no links; fixed
- Run 41000362327 (the first on the 4-machine path) finished in 5 min with nothing: the dying machine of run 1 had
  uploaded a 5 GB torso of the converted episode to the Drive cache, every machine took it ("no speech"), and the brief
  came out with 0 links because the PDF carries its URLs as link annotations, not as text.
- Bot: the Drive cache remembers the episode's size and a hit must match it; source.json is written only after the
  upload is checked against the local size; a conversion whose output is not 1920x1080 for the whole duration is
  dropped, never cached. PDF briefs now include their hyperlinks ("Links in the file:" block, pdfplumber hyperlinks).
- The broken cache files went to Drive's trash; the Higgsfield state forgets the brief (re-read with links) and the
  "no speech" verdict.

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
- rico: "still not centering correctly", "the transitions are [bad]", "the audio sounds weird", "the faces are not in
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
  [very] boring", "the screen keeps switching between 16:9 and 9:16 which is horrible and bad production", "have a
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
