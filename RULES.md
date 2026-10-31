# RULES — rico's editing and story rules (read before every cut)

Consolidated 2026-10-27 from PLAYBOOK.md, STORY_STRUCTURE.md and REVIEW_NOTES.md of the old system. rico's critique docs (campaigns/<c>/critiques/) extend this file; the newest critique wins.

## Hard limits (rico, 2026-10-27, updated 2026-10-28/29; history in CHANGELOG.md)
- Max 3 clips per campaign. Every clip passes the acceptance gates (scorecards/acceptance.md) and the judge bar of 80; under the bar = one re-edit, then the next best moment, at most 3 renders per slot (grade-and-retry, rico 2026-10-28). When nothing in a run reaches 80, clips that passed every gate at 75-79 go to 1_CHECK marked UNDER THE BAR.
- Quality beats speed (rico 2026-10-28: "amazing high tier quality is the most important"), but a campaign still finishes in one run.
- One platform per clip, by its category: YouTube = business/money, Instagram = celebrity/drama, TikTok = entertainment (bot/lanes.py, rico 2026-10-27 and 2026-10-29).
- No ad, brand or app-promo campaigns and no AI voice-over (rico 2026-10-27); only real content (podcasts, streams, shows, movies). No outside reframing service (rico 2026-10-29).
- Speaker labels in transcripts are not trusted; the face in the frame decides who is on camera.
- Outside photos or footage are never used; only the episode's own frames and the show's own graphics.
- Never edit or delete a post for 30 days after posting. Never permanently delete a file; move it.

---

# Playbook: what we've learned

This is the system's memory for how to do the job well. Every bot reads it before working: the shortlist picker, the editor, and the style checker. It's updated from `data/posts.csv`, and each rule needs evidence behind it, not a hunch.

Start: it's empty on purpose. Don't treat a pattern as a rule until it shows up in at least 10 posts.

## Working rules (proven by our data)

| Rule | Evidence (clips, dates) | Added |
|---|---|---|

## Experiments running (change one thing at a time)

| What we're testing | Version A | Version B | Clips each | Result |
|---|---|---|---|---|

## Campaign lessons

| Campaign | What they approved | What they rejected | Worth repeating? |
|---|---|---|---|

## Weekly review checklist (about 20 minutes, every Sunday)

1. Update `data/posts.csv` with 24h / 72h / 7d views (Content Rewards shows them).
2. Check Content Rewards payouts against counted views; flag any campaign that doesn't match.
3. If an account's median views drop sharply and stay down, slow posting on it and change style. That's an early ban warning.
4. Rank campaigns by **net $ per hour of your time**, not by views. Drop the bottom one.
5. Compare the top 5 and bottom 5 clips: hook, length, style, source. Write any repeat pattern into "Experiments" above.
6. Promote an experiment to a working rule only after 10+ clips each way.

## Editing rules from your reviews

From your review of the first drafts (2026-10-25). Every editor and style check follows these.

1. **Opener (spoiler):** a complete line of 3–6 seconds that makes sense on its own. A question plus its answer works best. Never a sentence fragment.
2. **Jump from the opener to the story:** a quick dip to black. Never a white flash (rico called it a "flashbang") and **never a pop-up label** like "Here's what happened". The opener must start and end on clean pauses, inside one camera shot: no stray shot and no frozen frame in the first 2 seconds.
3. **No clipped words:** every cut lands in the quietest moment between words. The clip ends on a finished sentence.
4. **Every clip needs a point.** Informative or motivational: the lesson is said in the clip. Funny: the setup and the punchline are both in it.
5. **True 9:16:** one person on camera means crop on them. Two people means a stacked split screen. B-roll means the whole picture on a blurred background.
6. **Opener:** start on the most interesting question, from anyone at the table, not just the guest. Use a jump-back teaser only when the line works as a punchline on its own (it worked for Prime and failed for the house clip).
7. **Use the show's own graphics.** When the episode shows a phone story, a definition card or b-roll, bring it forward: slide it in beside the speaker, or give it the bottom half. Never crop it in half.
8. **Steady camera:** the same camera angle always gets the same crop. Quick reaction shots get a single crop, not a split.
9. **Focus:** punch in (about 1.2x) on the key line or number.
10. **Ending:** stop before the next speaker's first sound, with a soft audio fade.
11. **Title (round 4):** in its own black band at the top, never over a face. Two lines max, one sentence per line, in Montserrat. Pronouns must be clear, and the payoff word goes in yellow. The campaign doesn't require a title (only a spoiler hook at the start), but we keep a short one.
12. **Would a normal person care?** Pick stories with stakes: money, a famous name, a failure, a surprise. Shop talk that only marketers care about gets rejected (the "how brands pay creators" clip).
13. **Let them finish, and read the captions.** End on the speaker's own wrap-up line. Before delivery, read the full caption text end to end (saved as captions.txt in the clip folder). Cut stutters and stray "mm-hmm"s from the captions.
14. **Show the product.** When the clip is about a brand (e.g. Bloom), get it on screen using the episode's own shots: a can on the table, the host drinking it, the show's b-roll. Never bring in outside images.
15. **B-roll never covers a face.** A tall phone story plays full size on its own (style "fit"), with the captions below it. Use only the show's moving footage, and skip any still screenshot or editor text the show put in front of it. The b-roll arrives exactly when the show's does, so the camera never shifts just before it (if the show starts with a still, play the moving footage slowed over the whole stretch, never a paused or held frame). No flicker of another camera at the start or end. At the end, hold the last clean frame and fade out, with captions still showing.
16. **Spelling.** Every caption word is spell-checked by the backtest (WARN on unknown words, listed in the SUMMARY; it was a FAIL until a real word, "unvirtuously", blocked a good clip on 2026-10-27). Real names and brands go in bot/spelling_allowlist.txt.
17. **When fixing, change only what rico flagged.** Don't redo parts rico already liked.
18. **The viewer must know what the story is about from the first second (full structure: the Story structure section below).** Prefer opening on the setup line that names who and what (e.g. "Kylie Jenner posted us in her story the other day"), with the hook text on screen for the first seconds carrying the spoiler (rule 42: no title band). Use a jump-back teaser only if it makes full sense with zero context; if a teaser is used, end it on someone else at the table reacting on camera, cut straight in, and cut those lines from the story so nothing repeats. Never let a split-second shot of another person flash after a jump (spec `video_swap`). After a b-roll the speaker must be centered again.
19. **Campaign requirements: never guess.** Read the MAIN campaign page first (it wins over reference files) and copy every requirement word for word into requirements.md, **per platform**: tags, hashtags, caption rules, length, platforms. Tags differ per platform (Iced Coffee Hour: Instagram @greglav, YouTube @GregLaVecchia, both plus @theicedcoffeehour). Anything unclear is a STOP: ask rico for a screenshot of the campaign page before posting, never post with a gap. bot/brief.py reads the tags from the requirements and bot/post_kit.py puts them in the POST KIT per platform. On YouTube the tags go in the **title and** the description (Shorts show the title and hide the description).
20. **Thumbnail (bot/thumbnail.py; rico 2026-10-29: "make sure it's really good", then "very creepy, no one would want to watch that, the text is bad").** A frame from the episode itself, never an outside image (the briefs ban them). The frame is picked to be CLICKED, not to be loud: a frontal, sharp, mid-size face (no postage stamp, no pore-level close-up, zoom at most 1.5x), NOT at a shout (the sound at that instant is measured: a peak means a mid-scream face, which is grotesque as a still; a quiet beat is a reaction shot), the close-up of the lead slightly ahead, two faces only when both fit one 9:16 crop. Women first (rico 2026-10-29: "females get more clicks, let's lean in on that") is applied BY EYE: the reviewer pins a frame with a woman via `thumb_t` and only calls it that after rico confirms it. The automatic version (bot/models/genderage.onnx, InsightFace, via OpenCV) is OFF (`thumbnail.WOMAN_BOOST = 0`): on DIGGER it called two cats, the man in the parka and the long-haired man at the window women, and the bot told rico the window frame was a woman. Never state who or what is in a frame as fact without rico's confirmation. Text is SHORT: 2-6 words (the reviewer's `thumb_text` in plan.json, else a cut of the hook: a clause with the number or emphasis word, else the opening words with "..."), huge Montserrat Black, white with ONE yellow word (a number or money first, else the emphasis word, else the last word), in the upper third, or the lower third when the face sits high. The picture gets a light pop grade (contrast, colour, lift on dark frames, soft vignette), no heavy black gradient. Beside the PNG a 2x2 OPTIONS sheet (`<clip>_thumbnail_options.jpg`) shows the 4 best different frames with their times: rico says "clip 01, option 3" and the reviewer pins `thumb_t` (episode seconds) in plan.json; the next run remakes the thumbnail. Saved as thumbnail.png beside the clip (1_CHECK and 3_APPROVED) and appended as the clip's last two frames, because YouTube Shorts and TikTok take no thumbnail file: in the app, pick the LAST frame of the video as the cover. Instagram Reels take the PNG as a custom cover. A remade thumbnail replaces the old last frames (THUMB_VERSION in run.py). QA ignores the appended frames.
21. **Smooth transitions, checked by machine and by eye.** A cut edge sits on the show's own camera cut when one is within 0.6 s (no split-second shot of the wrong person), the show's white wipe frames are dropped (`deflash`), captions move with the layout, and audio is normalised through a wav so the packet timestamps stay steady (podcasts: two-pass loudnorm; movies, streams and concerts: one fixed gain to -14 LUFS plus a limiter at -3 dBFS, because loudnorm went dynamic on music, rico 2026-10-29 "the audio sounds weird"). The backtest FAILs on any stray hard cut in the first/last 1.5 s or at a join, and on any flash frame; a hard cut inside the show's b-roll is only a WARN. **Crop jumps** (2026-10-29, "the transitions are ass"): every join we make inside one shot is compared with the source; a picture jump where the source has no cut is a crop jump, two of them FAIL the clip. Nothing reaches 1_CHECK without every hard gate in scorecards/acceptance.md passing and the judge at 80 or more (75-79 only marked UNDER THE BAR when nothing reached 80).

Round-by-round reasons: rico's critiques in campaigns/<c>/critiques/.
22. **The speaker is centred, always (rico, 2026-10-26: "horribly off centre").** The editor tracks the face through the whole shot with the YuNet neural detector (2026-10-29; the Haar cascades missed turned heads and small actors): ONE identity per shot, the hit nearest the chosen actor, a weak hit may only continue an identity, a hit more than 15% away is somebody else, median-smoothed, and when the speaker turns away the window keeps the other face inside it. The window glides after the face with a dead zone of 6% of the WINDOW width (podcasts 4% of the source), so the face sits in the middle third and never touches an edge; the glide never restarts mid-move. With a side card the face sits at one third and the card takes the other side, never over the face. The backtest measures it on the finished picture: FAIL when the face is more than 12% off centre for over 15% of the time.
23. **Never a format switch: ONE 9:16 look per clip (rico 2026-10-28: "switching between 16:9 and 9:16 is horrible").** No letterboxed or whole-frame 16:9 picture inside the short, ever, not even for a shot with text in it. Podcasts: the show's wide two-shot becomes a stacked split on both people (small faces found at full resolution). Movies, streams, concerts: the crop follows the actors and punches in up to 1.5x on wide shots, a two-shot is cropped on whoever talks, never split; burned-in text steers the crop only when it is a real card (35%+ wide, or centred with nobody on screen), and a credit card at a moment's edge is trimmed to its real end (rico 2026-10-29: "internal text in the show is cut off"; qa_check "Footage text cut off"). B-roll with nobody in it gets a full-height 9:16 window. The backtest FAILs any letterbox segment. **Never an empty room:** when the detector misses one of the two small faces in the wide shot, the editor falls back to the pair it found earlier in the clip, then to the spec's `wide_split` positions (the spec's two seats, e.g. left 0.22, right 0.74), so the window is never cropped down the middle of the set; the backtest FAILs any single-speaker stretch of 1.5 s with no face ("Somebody in frame"). Caught on the first v2 pass, 2026-10-26.
24. **No dead air.** Any pause over 0.7 s inside the cut is removed (0.16 s kept each side), and every join (between moments or across a removed pause) alternates a light punch-in (1.0 / 1.06) so it reads as an edit. The backtest FAILs silence over 0.8 s.
25. **A graphic is boxed at its biggest.** Measure the show's card at the last frame it is on screen (the "2,500 balls" card grew a third line 8 s in) so the window never has to jump and nothing leaks beside the card. Cards leave on the show's own cut (`hard_out`).
26. **B-roll means the show's own footage, more of it, never outside material.** The campaign allows only the episode: no old photos, no stock, no web images (rico asked for a boxer photo of Mike Agassi: not allowed; the show's own Mike Agassi card is). So before cutting, map every graphic, b-roll shot and card in the episode (bot/find_moments.py lists them) and prefer moments that have one. Add our own visual change at least every 6–8 s: a card, a punch-in on the key word, a split, a camera cut. Our own **callouts** (a big yellow text card for the number or name the speaker just said: "$1,000,000 A YEAR", "ADDICTED TO METH") are text like the captions, so they are allowed; spec `"callouts"`, placed under the chin or above the split, never over a face, with the whoosh.
27. **Hook and story are graded by a separate judge before rico sees anything** (scorecards/judgment.md, bot/judge_clip.py). The judge scores: would a stranger stop scrolling in 2 s, is there a stake a normal person cares about (money, a famous name, a failure, a surprise, a secret), does it pay off, does it end on a finished thought, framing and pace. Bar 80 since 2026-10-29 (70 at first, 78 on 2026-10-28): under it, one re-edit, then the next moment; the judge writes judge_report.md into the clip folder and its area breakdown (hook 20, pace 10, variety 15, framing 10, story 10, entertainment 10, comedy 5, captions 10, length 10) into data/last_run.log. Framing points come from the acceptance gates; a montage (median shot under 1.2 s) and a title without a number, question, quote or name lose points.
28. **Moments are found by reading the whole episode, not by skimming** (bot/find_moments.py + scorecards/entertainment.md): every 20–60 s window is scored for stakes, names, numbers, contrast ("but", "actually", "turns out"), a question-and-answer shape, reactions from the table and the show's graphics, then the top candidates are read in full and judged. The clip we cut is the best of the episode, not the first good one.
29. **Small sounds: allowed, subtle, only on reveals.** Most briefs have no rule on sound. A soft synthesised whoosh (-22 dB, 0.45 s) under a card sliding in is on by spec flag `"sfx": true`; never over speech, never a music bed unless a campaign asks for one. rico judges on v2 whether it stays.
30. **The first 5 seconds are the whole game.** Open on Mark's (the speaker's) close-up, on the line that names who/what, with the strongest visual already on screen; the title carries the spoiler (Story structure below). A clip that starts on a wide shot, a pronoun, or a slow run-up is re-cut.
31. **Text is heavy Montserrat everywhere (rico 2026-10-28: "the font and shape isn't nice or good size").** ExtraBold title (max 84-88 px, up to 3 lines), Black captions (~86 px, outline 8), 2-4 word phrases held 0.6 s+, numbers whole, swearing masked unless the spec says `profanity: "show"`. Bebas Neue and Poppins were rejected.
32. **Actors fill the frame (rico 2026-10-28/29: "not focusing on actors", "faces are not in frame").** On movies faces from 2.5% of the width count and the window punches in on them; qa_check measures face presence (80%+ of the seconds) and face height (12%+ of the picture) on the finished clip, and "Somebody in frame" FAILs an empty window of 1.5 s (a movie's own scenery cut may run 3 s).
33. **One platform per clip (rico 2026-10-27, 2026-10-29).** bot/lanes.py reads the clip's own words: YouTube = business/money, Instagram = celebrity/pop culture/drama, TikTok = entertainment. The SUMMARY shows the lane before rico approves; the POST KIT lists only that platform; the reviewer can pin `"lane"` in plan.json. Never post one clip to all three.

---

34. **The pitch (rico 2026-10-29: "reading the script / captions and the bot deciding if it's good or entertaining enough per the campaign's style, so we aren't wasting time making clips").** Before any render, bot/pitch.py reads the WORDS of every candidate (reviewer pick or scorecard moment) against the campaign's profile and genre mix: hook (name, number, question or quote in the title; a first line that names who and what), story (stakes, a contrast, a finished ending, no podcast back-references), entertainment and comedy on the campaign's genres, pace and length. Under 60/100 the moment is not rendered. The SUMMARY lists every pitch with its score, verdict and reasons. When nothing passes, the single best pitch is rendered anyway, marked PITCH UNDER THE BAR, so a campaign still gets one try and rico sees why the material is thin.

35. **Each campaign gets its own look (rico 2026-10-29: "ensure editing is altered to represent the style of the campaign").** The profile (podcast / cinematic / stream / performance, RULES 25) sets the base; the reviewer pins the campaign's look in plan.json `brief_overrides.look`: accent colour (ASS BGR, e.g. `&H2BC6FF&` warm gold for a movie, `&H00D7FF&` yellow for a podcast), caption size, words per caption, title size, outline and shadow. Fonts stay Montserrat (rule 31). The SUMMARY's run notes show `style:` and `look:` so the choice is visible on every run.

36. **Accounts and campaign fit (rico 2026-10-29: "distinctly categorize my different accounts and what I post there and have a better judgment on the campaigns selected").** config/accounts.json holds each account's identity (what it posts, what it never posts, see the Accounts section below). The scan rejects a campaign that fits none of the three identities (no clear topic) and any promo: brand, app, product, token, or game footage with no person in it (the MW4 "Campaign Moments" offer of 2026-10-29 was withdrawn for this). The JOIN doc names the account the campaign would feed. A campaign's pay-out pace decides whether it is "close to ending" (rico 2026-10-29): Content Rewards campaigns have no end date, they close when the budget is spent, so the scan estimates the days left from budget left / (paid out ÷ days since launch) and stops under 10 days unless the title says weekly or monthly (a refilling pot). Rules and reference files are hidden until rico joins; `pages.yml` reads what a campaign page shows to a visitor. The BOT picks the campaign (rico 2026-10-30: "choose based on your scorecard"): the top card that passes every stop, earlier offers included unless rico killed them; rico is told the pick and the runner-up, never asked to choose. Reach-style campaigns (dedicated or niche-matching account required) are stopped since TJR.

37. **The bot stops instead of repeating itself (audit 2026-10-29).** A campaign that kept nothing three runs in a row waits for a note in 2_REDO or a plan.json; moments rendered and dropped are not picked again by the scorecard (`tried_moments`); the POST KIT always lists every approved clip; the campaign scan runs on its own hourly workflow only. A Drive error stops the run loudly (noted in state) rather than reading as empty folders.

38. **Required watermarks and per-platform handles (Higgsfield 20VC, 2026-10-30).** When the brief says "watermark" (or a PNG named watermark/logo sits in 0_START), the bot keeps that PNG on screen the whole clip: 500 px wide in the top left corner of the frame, above captions, callouts and the hook text, never covered. Several kit variants: the most opaque one is used, it reads on any picture. A brief that names handles per platform ("YouTube: @A + @B / Instagram: @c @d") gets a POST KIT with only that platform's handles on each post. The BRIEF doc shows both.

39. **A still camera and the brief's own moments (rico 2026-10-30: "the clips move too much because of the clipping on the face, very distracting"; "I lost interest within the first 4 seconds").** Talking shows: the crop is locked on the speaker's median position for the shot and re-frames only when the face stays more than 10% of the width away for a full second, then glides over 1.2 s (render_clip.pan_keys hold=4; movies keep the fast 6% follow rico approved on DIGGER). Moment choice: when the brief lists its own clip ideas with times (brief.moments, e.g. Clipfarm's "HOOK / TIME / KEEP IN MIND" table), those are cut FIRST, in the brief's order, with the brief's line as the title; the scorecard's picks come behind them. A clip never opens on a filler sentence ("Because, I mean...", "And so..."): plan.FILLER_START skips those windows. The brief reader takes the ideas table in any layout a PDF produces (hook wrapped over the time line, hook closed right before the time); two-part ideas and ranges under 15 s are left out. A failed clip's one re-edit fixes what failed: a clipped word at a cut or an unfinished ending moves the cut to sentence edges inside the brief's length window. The centring gate allows 17% off centre per frame on talking shows (the still camera's 10% dead zone plus detector jitter), 12% on movies.

40. **A second grading pass: the audience read (rico 2026-10-30: "the clip cuts out in a horrible position, the speaker can't talk, boring and hard to understand; improve grading quality and entertainment, add a second phase of engagement scoring").** bot/engage.py scores every clip 0-100 from its spoken words as a stranger hears them (cold open 25, clarity 20, payoff 20, retention 20, focus 15; bar 70) with four hard gates: no host preamble or pointer back in the first sentence, restarts and fillers under 8% of the words, the last line is the answer (no aside, no hanging question, no one-word "Yes."), no two flat 5-second windows in a row. The read runs before rendering (the pitch rejects the moment), when the cut's edges are chosen (plan.refine takes the sentence window with the best read), and on the finished clip (a gate failure counts like a QA FAIL; the re-edit moves the cut to the read's start and end). Gates and areas: scorecards/acceptance.md. Also gates: a pointer start ("This industry still gonna be...") with no number, name or question; an ending on the host's next lead-in ("You're at a billion in revenue now."). Editing on talking shows: every dollar figure or number the speaker says gets a big number card (plan.auto_callouts, max 3 per clip), and the judge takes no points off for the still camera.

41. **The story format is a gate (rico 2026-10-31: "the point is to not rely on the title and for them to say it... both clips yap for the first few seconds... the storyline, 5 Ws, the progression and the hook are weak").** Every talking-show clip must say its headline in the first 6 s (a money figure or big number, the title's name, or the host's short question naming the subject), name its subject or say 30% of the title's words in the first 10 s, carry new stakes after the hook, and end on a line that lands a stake or the title's claim. bot/engage.py (areas: open 25, story 20, payoff 20, retention 20, clarity 15; bar 70) fails a clip on any of these at the pitch, when the edges are chosen (plan.refine) and on the finished clip. Full structure: the Story structure section below.

42. **No title band; one caption spot; a who-line (rico 2026-10-31 02:02: "the text captions are not consistent, very hard to track, sometimes above, other bottom, other center; keep it nice and nice to look at; do we need an above header? is that required by the campaign? because it looks ugly" + "who is this guy, what is the topic").** The picture fills the whole 9:16 frame (render_clip.TOP = 0). The campaign's hook text is a timed overlay, not a band: under the watermark for the first 5 s, then it fades (the Higgsfield brief asks for the hook "in the first few seconds, like a spoiler", nothing more). Under the hook, in the accent colour, a who-line names the speaker and why they matter, from the brief's wording (brief.speaker_tag: "Alex built Higgsfield, an AI video company" -> "Alex Mashrabov · built Higgsfield (AI video)") or a hand-written "speaker_tag" in the campaign's state. Captions sit at ONE spot the whole clip (render_clip.CAP_DEFAULT, y = 1400 of 1920) and number cards at one spot above them (CALLOUT_Y); talking shows never split the picture any more: a two-shot is cropped on whoever talks (mouth motion), punched in up to 1.35x when the faces are small. The watermark sits in the top left corner. QA: a face under the hook text in the first seconds is flagged ("Faces clear of the title").

# Accounts: what each one posts (config/accounts.json)

| Account | Posts | Never |
|---|---|---|
| YouTube @fedsaa | business, money, careers, founders, investing, self-help with stakes: podcast and interview moments where someone with a track record says something a stranger can use | product demos, app promos, brand ads, gaming, music, drama |
| Instagram @fesavoo | celebrity, pop culture, drama, gossip, relationships, dating, reality TV, fashion and beauty talk: moments people screenshot and send to a friend | finance talk, gaming, software, brand ads |
| TikTok (handle TBD) | entertainment: streamers, gaming WITH a personality on screen, comedy, music and live performance, movie and show scenes with actors, sports moments | silent game footage, product trailers, app promos, brand ads, AI voice-overs |

A campaign must fit exactly one account or it is rejected at the scan; a clip is posted to the one account its own words fit (rule 33).

# Story structure: how every short must flow

rico approved this structure on 2026-10-25 with the Kylie Jenner clip (ICH-004 v8) and rewrote the bar on 2026-10-31 after
the Higgsfield clips ("the point is to not rely on the title and for them to say it; both clips yap for the first few
seconds; the storyline, the 5 Ws, the progression and the hook are weak"). Every clip follows it. The bot checks it
three times (bot/engage.py, the audience read): when it chooses the cut's edges, before rendering, and on the finished clip.

## The rule in one line
A stranger who has never seen the show must understand **who, what and why it matters from the first spoken line, with
the title muted**, and the story then plays **in order** to a payoff the speaker says out loud.

## The 5 beats (and what the bot measures)
| # | Beat | What it does | Gate (talking shows) |
|---|---|---|---|
| 1 | **Hook line (0-6 s)** | The first sentence IS the headline: a dollar figure, a big number, the name from the title or the claim, in the speaker's own words; or the host's short question that names the subject ("So how much do you spend on models per month?"). No setup, no "and remember...", no "but fundamentally, I think...". | a money figure / number of two digits or more / million-billion-percent, or the title's name, or 40% of the title's words, is said inside 6 s; or the first line is a question of 12 words or fewer naming the subject |
| 2 | **Who / what (0-10 s)** | Within ten seconds the viewer can say who is talking about what without reading the title: a company or person is named, or the title's own words are said. | a name (Higgsfield, Google, Yuri) or 30% of the title's words inside 10 s |
| 3 | **Why / how (the build)** | The reason or the contrast behind the hook, in the order it was said: "because...", "the problem is...", "but...". New numbers, names and stakes keep arriving; nothing is said twice. | points: a reason or contrast after the hook; 3 distinct stakes with one after the hook; at most 2 questions. Gate: fewer than 2 stakes in the whole clip |
| 4 | **Payoff (last line)** | The last sentence lands the answer: a number, a stake or the title's claim, by the speaker. Never a host lead-in ("You're at a billion now"), a compliment on the question ("that's the best question of the show"), an aside ("by the way"), a hanging question or a one-word "Yes." | the last line passes engage.bad_end and carries a stake or the title's words |
| 5 | **Hook + who-line (0-5 s)** | The hook text sits at the top of the picture for the first 5 s and fades; under it a who-line says who is talking and why they matter ("Alex Mashrabov · Founder of Higgsfield AI"). It repeats what is said; it is never the only place the story is told. No permanent band. | the title has a name, a number, a question or a quote (judge); the who-line comes from the brief (brief.speaker_tag) or the campaign's state |

## Do
- **Start on the line that says it.** When the headline is said late in a sentence, start on the host's short question before it, or on the next sentence that says it. plan.refine searches up to 3 sentences earlier and 6 later for the window with the best read inside the brief's length.
- **Cut only at pauses.** Whisper's sentence breaks with no gap ("...the same Did you know") leave clipped words; a window whose edges have no pause is avoided.
- **Play the story in order.** Cut dead air, never reorder events. A teaser (the payoff line first) only when rico asks for it on that clip.
- **Keep the table's reactions** ("Wow", "How?") when they are short; never end on them.
- **Numbers on screen.** Every dollar figure or number a talking show says gets a big card (plan.auto_callouts).
- **30-60 s** or the brief's window, as long as the story needs and no longer.

## Don't
- No line that needs the episode to make sense ("this", "that", "he" with no name before it; "as I was saying").
- No clip whose first 5 s a scroller can skip: filler, setup, host preamble, a pointer back.
- No ending on the host turning the page, a compliment, an aside, a question or a fragment.
- No pop-up labels and no white flashes (rule 2 above).

## Transitions (rico, 2026-10-26: "weird cuts and transitions")
- A join between two moments is made on a camera cut of the show when one is near, otherwise with a punch-in change, never a bare same-camera jump.
- A card or b-roll arrives on the word it illustrates and leaves on the show's own cut; the speaker is centred before and after.
- No letterbox, no format switch, no empty-room frame, no face at the edge.

## Check before sending to rico
1. Mute the title and read only the first spoken line. Do I know who and what this is about? If not, start later.
2. Read captions.txt top to bottom. Does it read like a short story with a start, a middle and an ending?
3. Does the payoff the title promises actually happen in the clip?
4. Does it end on the speaker's own finished sentence?

If any answer is no, re-cut before sending.
