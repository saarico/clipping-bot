# Acceptance criteria: when a clip may leave the bot

rico, 2026-10-29: "a full quality inspection is ideal and necessary", "have better scoring cards", "have better rejecting meter". This is the inspection. Every line is measured on the finished mp4 by `bot/qa_check.py` (table in `qa_report.md`) or `bot/judge_clip.py` (`judge_report.md`). A clip goes to 1_CHECK only when **every gate passes and the judge scores 80+**. Under that: one re-edit, then the next best moment (`bot/pipeline.try_until`). A clip that fails any hard gate is never uploaded. When no clip of a run reaches 80, the best clips that passed **every** gate at 75-79 are uploaded marked "UNDER THE BAR" in the summary (run 7, 2026-10-29: two clean clips at 76 and 75 and an empty folder helps nobody); rico decides.

## Hard gates (any FAIL = rejected)

| Gate | Measured how | Pass |
|---|---|---|
| One 9:16 look | layout of every segment | no segment shows the 16:9 picture whole (no format switch) |
| Actors fill the frame | YuNet face detector + HOG person detector once a second on the output | a face or person in 80%+ of the seconds (60% = reject), typical face height 12%+ of the picture (under 9% = reject) |
| Speaker centred | surest face in the upper 72% of the picture, every 0.5 s | face centre within 12% of the middle in 90%+ of frames |
| Somebody in frame | face (8%+ of width on movies, 25%+ on podcasts) or a person | no empty stretch of 1.5 s; a movie's own scenery cut (a segment the renderer framed wide) may run 3 s |
| Footage text cut off | letter rows touching the frame edge, once a second | at most one second |
| Crop jumps | at every join we made: output jump vs source jump at the same moment | no two joins where the source is continuous but the picture jumps; at most 8 joins per 10 s |
| Faces clear of the title | face boxes vs the hook text (first 5 s) and the top edge | no face under the hook text, no head cut off at the top (warn at 1-2 frames, fail above) |
| Captions readable | caption events | 2-6 words per caption, none under 0.35 s, numbers whole, swearing masked |
| Captions cover the whole clip | spoken words vs captions | no spoken word missing, first caption inside 1 s, last within 2 s of the end |
| Caption spelling | pyspellchecker + allowlist | unknown words = warning for the reviewer (names), never a wall of them |
| Nothing said twice | 6-word repeats | none (a declared teaser is allowed) |
| Ends on a finished sentence | last caption | ends with . ? ! |
| Audio | ebur128 + silencedetect | -14 LUFS within 3.5 LU, peak under -0.5 dBFS, no silence over 2 s |
| Format | ffprobe | 1080x1920, 30 fps, 10-90 s, AAC audio |
| Picture | blackdetect / freezedetect | no black, frozen or flickering stretch |
| Cut edges | word times vs cut points | no clipped word at either end |
| Audience read: cold open | first sentence and first 4 s of speech (bot/engage.py) | no host preamble or pointer back ("I do just want to go back to part of the story"); something to grab (a number, a stake, a name, a claim, a question) inside 4 s |
| Audience read: clarity | restarts + fillers over the clip's words | under 8% of the words |
| Audience read: payoff | the last sentence | not an aside ("By the way, Jason asked this in May"), not a hanging question, not a one-word "Yes."; no question in the last 10 s left unanswered |
| Audience read: hook line | the first 6 s of speech vs the title (bot/engage.py) | a money figure, a number of 2+ digits, million/billion/percent, the title's name or 40% of its words is said; or the first line is a question of 12 words or fewer naming the subject |
| Audience read: who / what | the first 10 s of speech | a name (company, person) is said, or 30% of the title's words |
| Audience read: payoff lands | the last sentence | carries a number, a stake or the title's words; never a compliment on the question, a host lead-in, an aside or a question |
| Audience read: progression | distinct stakes (numbers, names, money, failure, surprise) over the clip | at least 2 |
| Audience read: retention | 5-second windows of the spoken words | never three windows in a row with nothing to hold on to (number, stake, name, question, contrast, laugh, family/hardship); under 40% dead windows |

Movies, streams and concerts turn a few podcast rules into warnings (`profiles.py soft_qa`): fast cuts, a quiet opener, an unfinished sentence under music. Centring, somebody in frame, actor size, crop jumps, text cut off and audio are **never** soft.

## The audience read (0-100, bar 70) - the second grading pass (2026-10-30, story format 2026-10-31)

bot/engage.py reads the spoken words the way a stranger scrolling past hears them: cold open 25 (the hook line said in 6 s), story 20 (who/what said in 10 s, why/how, progression, one
idea), payoff 20 (the last line lands), retention 20, clarity 15. It runs three times: on a
candidate before rendering (pitch.score: a gate failure or a read under 70 rejects the moment), on the edges when the
cut is chosen (plan.refine picks the sentence window with the best read), and on the finished clip (engage_report.md;
a gate failure counts like a QA FAIL and the re-edit moves the cut to where the read says the clip should start and
end). Under 70 with no gate failure: the clip is under the bar.

## The judge (0-100, bar 80)
hook 20 · pace 10 · variety 15 (a montage of sub-second shots loses 6) · framing 10 (the gates above feed it) · story 10 · entertainment 10 (genre mix) · comedy 5 · captions 10 · length 10. The title must carry a name, a number, a question or a quote, on every kind of footage.

## What the inspection cannot see
Whether the moment is actually funny or interesting to a stranger. That is the entertainment scorecard (`scorecards/entertainment.md`) at pick time and rico's own eye at review time. When rico rejects a clip, the fix goes into one of these tables, so the same mistake is caught by the machine next time.
