# RULES — rico's editing and story rules (read before every cut)

Consolidated 2026-10-27 from PLAYBOOK.md, STORY_STRUCTURE.md and REVIEW_NOTES.md of the old system. rico's critique docs (campaigns/<c>/critiques/) extend this file; the newest critique wins.

## Hard limits (rico, 2026-10-27)
- Max 3 clips per campaign. One render, one QA pass, one judge pass per clip. Under the bar = next moment, never a re-cut loop.
- Speed over polish. A campaign goes from requirements to 3 clips in 1_CHECK in one run.
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
18. **The viewer must know what the story is about from the first second (full structure: the Story structure section below).** Prefer opening on the setup line that names who and what (e.g. "Kylie Jenner posted us in her story the other day"), with the title band carrying the spoiler. Use a jump-back teaser only if it makes full sense with zero context; if a teaser is used, end it on someone else at the table reacting on camera, cut straight in, and cut those lines from the story so nothing repeats. Never let a split-second shot of another person flash after a jump (spec `video_swap`). After a b-roll the speaker must be centered again.
19. **Campaign requirements: never guess.** Read the MAIN campaign page first (it wins over reference files) and copy every requirement word for word into requirements.md, **per platform**: tags, hashtags, caption rules, length, platforms. Tags differ per platform (Iced Coffee Hour: Instagram @greglav, YouTube @GregLaVecchia, both plus @theicedcoffeehour). Anything unclear is a STOP: ask rico for a screenshot of the campaign page before posting, never post with a gap. bot/brief.py reads the tags from the requirements and bot/post_kit.py puts them in the POST KIT per platform. On YouTube the tags go in the **title and** the description (Shorts show the title and hide the description).
20. **Thumbnail (not built in the rebuild yet, planned):** the hook visual on top, the speaker reacting below (eyes open, mid-gesture), 2 lines of big text in the middle (white plus yellow). Only frames from the episode. Until the tool is ported, pick the frame in the app at the clip's best b-roll moment.
21. **Smooth transitions, checked by machine and by eye.** A cut edge sits on the show's own camera cut when one is within 0.6 s (no split-second shot of the wrong person), the show's white wipe frames are dropped (`deflash`), captions move with the layout, and audio is normalised in two passes (no pumping) through a wav, so the packet timestamps stay steady (bunched timestamps sound sped-up on YouTube; the backtest FAILs them). The backtest FAILs on any stray hard cut in the first/last 1.5 s or at a join, and on any flash frame; a hard cut inside the show's b-roll is only a WARN. Nothing reaches 1_CHECK without qa_check PASS (bot/qa_check.py lists every check) and the machine judge at 70 or more.

Round-by-round reasons: rico's critiques in campaigns/<c>/critiques/.
22. **The speaker is centred, always (rico, 2026-10-26: "horribly off centre").** The editor tracks the face through the whole shot (frontal detector first, the hit nearest the last position, median-smoothed) and the window glides after it with a dead zone, so the face sits in the middle third and never touches an edge. With a side card the face sits at one third and the card takes the other side, never over the face. The backtest measures it on the finished picture: FAIL when the face is more than 12% off centre for over 15% of the time.
23. **Never a format switch.** No letterboxed 16:9 picture inside the short, ever. The show's wide two-shot becomes a stacked split on both people (small faces found at full resolution); b-roll with nobody in it gets a full-height 9:16 window. The backtest FAILs any letterbox segment. **Never an empty room:** when the detector misses one of the two small faces in the wide shot, the editor falls back to the pair it found earlier in the clip, then to the spec's `wide_split` positions (Solved: Mark left 0.22, Drew right 0.74), so the window is never cropped down the middle of the set; the backtest FAILs any single-speaker stretch of 1.5 s with no face ("Somebody in frame"). Caught on the first v2 pass, 2026-10-26.
24. **No dead air.** Any pause over 0.7 s inside the cut is removed (0.16 s kept each side), and every join (between moments or across a removed pause) alternates a light punch-in (1.0 / 1.06) so it reads as an edit. The backtest FAILs silence over 0.8 s.
25. **A graphic is boxed at its biggest.** Measure the show's card at the last frame it is on screen (the "2,500 balls" card grew a third line 8 s in) so the window never has to jump and nothing leaks beside the card. Cards leave on the show's own cut (`hard_out`).
26. **B-roll means the show's own footage, more of it, never outside material.** The campaign allows only the episode: no old photos, no stock, no web images (rico asked for a boxer photo of Mike Agassi: not allowed; the show's own Mike Agassi card is). So before cutting, map every graphic, b-roll shot and card in the episode (bot/find_moments.py lists them) and prefer moments that have one. Add our own visual change at least every 6–8 s: a card, a punch-in on the key word, a split, a camera cut. Our own **callouts** (a big yellow text card for the number or name the speaker just said: "$1,000,000 A YEAR", "ADDICTED TO METH") are text like the captions, so they are allowed; spec `"callouts"`, placed under the chin or above the split, never over a face, with the whoosh.
27. **Hook and story are graded by a separate judge before rico sees anything** (scorecards/judgment.md, bot/judge_clip.py). The judge scores: would a stranger stop scrolling in 2 s, is there a stake a normal person cares about (money, a famous name, a failure, a surprise, a secret), does it pay off, does it end on a finished thought, framing and pace. Under 70 = dropped, the next moment is tried (no re-cut loop). The judge writes judge_report.md into the clip folder.
28. **Moments are found by reading the whole episode, not by skimming** (bot/find_moments.py + scorecards/entertainment.md): every 20–60 s window is scored for stakes, names, numbers, contrast ("but", "actually", "turns out"), a question-and-answer shape, reactions from the table and the show's graphics, then the top candidates are read in full and judged. The clip we cut is the best of the episode, not the first good one.
29. **Small sounds: allowed, subtle, only on reveals.** The Manson brief has no rule on sound. A soft synthesised whoosh (-22 dB, 0.45 s) under a card sliding in is on by spec flag `"sfx": true`; never over speech, never a music bed unless a campaign asks for one. rico judges on v2 whether it stays.
30. **The first 5 seconds are the whole game.** Open on Mark's (the speaker's) close-up, on the line that names who/what, with the strongest visual already on screen; the title carries the spoiler (Story structure below). A clip that starts on a wide shot, a pronoun, or a slow run-up is re-cut.

---

# Story structure: how every short must flow

rico approved this structure on 2026-10-25 with the Kylie Jenner clip (ICH-004 v8): "I love the context behind the post and the way the viewer can easily follow along." Every new clip follows it. Read it before picking the cut, and check the finished clip against it before sending it to rico.

## The rule in one line
A stranger who has never seen the show must understand **who, what and why it matters** from the first second, and the story then plays **in order** to its payoff.

## The 5 beats
| # | Beat | What it does | Kylie example |
|---|---|---|---|
| 1 | **Title band (the spoiler)** | It sits on screen from frame 1 and promises the payoff, so people keep watching. | "Kylie Jenner posted Bloom for free. Sales didn't move." |
| 2 | **Setup line (first 1–3 s)** | The speaker's own sentence names who and what. It's a line a stranger understands with zero context. | "Kylie Jenner posted us in her story the other day…" |
| 3 | **Build** | The details that raise the stakes, in the order they were said. Show the thing being talked about (the show's own b-roll). | She tried three Shirley Temples, called Bloom the winner, and it was totally organic. |
| 4 | **Turn / payoff** | The surprise the title promised. A reaction from someone else at the table makes it land. | "We didn't get one Amazon search… not one tick-up in sales." Host: "How?" |
| 5 | **Wrap-up** | The speaker's own explanation or lesson, ending on a finished sentence. | "Four years ago we'd be sold out in 24 hours… people are done buying what celebrities tell them to." |

## Do
- **Start where a stranger understands it.** The first spoken line names the person, brand or number. Skip lines that point backwards ("as I was mentioning earlier", "what's also interesting is…", "that's why…").
- **Play the story in order.** Cut out dead parts, but never reorder events.
- **Let the title carry the spoiler.** The campaign asks for a spoiler hook at the start, and the title band does that job.
- **Have the visual on screen when the setup line starts.** For example, her story video was already playing on "Kylie Jenner posted us…". No slide-in from an empty screen, no paused frames, and the speaker centered after the b-roll.
- **Keep reactions from the table** ("How?", "Wow", "No way"). They tell the viewer this is the surprising part.
- **Aim for 40–60 s**, as long as the story needs and no longer.

## Don't
- **No jump-back teaser** that drops the viewer mid-story. It was tried 3 times on Kylie and rico found it confusing every time. Use one only when the line makes complete sense with zero context, and even then the setup-first version usually wins.
- No line that needs the episode to make sense ("this", "that", "he" with no name before it).
- Never say anything twice.
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
