# Entertainment scorecard: which moments of the episode get cut

Run by bot/find_moments.py over the whole transcript (every 20-60 s window), used by bot/plan.py when no reviewer plan exists. The reviewer (Claude) reads the top candidates in full and writes campaigns/<c>/plan.json with the 3 picks, hooks, callouts and the reasoning that goes into SUMMARY.


rico, 2026-10-26: "Are you able to read the entire video and judge and create a judgement and entertainment bot to find the best entertainment clip to make?" This is that process. It replaces "skim the transcript and pick the first good story".

## Steps
1. **Transcribe the whole episode** (OpusClip AI Producer, pieces of 30 min) into `words.json`.
2. **Map the show's graphics** with `bot/graphics_map.py <episode.mp4> gfx.json`: every card, photo and bottom strip with its time and box. These are our only b-roll (the campaign forbids outside material), so moments that have one score higher and the boxes go straight into the spec.
3. **Score every window** with `bot/find_moments.py words.json --graphics gfx.json`: all 20-60 s stretches that start and end on a sentence, scored for stakes (money, fame, failure, surprise, emotion, numbers), shape (question + answer, story markers, contrast, reactions), clarity of the first line, pace, visuals, payoff and length. Podcast back-references ("we talked about this in the shame episode") are penalised hard: a stranger is lost.
4. **Read the top 15 in full** (`candidates.md`), as a stranger. Keep only moments with a stake a normal person feels and a payoff that lands. Write the title first: if no 10-word title makes someone stop, the moment is out.
5. **Cut, then judge** (scorecards/judgment.md). Only clips over the bar go to rico.

## Genres and media types (2026-10-28, rico: "go more into different genres and different types of media", "ensure comedy grade is also present")
Two things describe a campaign. The **media profile** (bot/profiles.py: podcast, cinematic, stream, performance) says how the footage behaves and sets pace targets, what counts as a framing failure, and the fonts. The **genre mix** (bot/genres.py: comedy, drama, action, horror, romance, gossip, business, selfhelp, truecrime, sports, gaming, music) says what the audience came for; it is read from the brief, then the transcript, or pinned by the reviewer in plan.json `brief_overrides.genres`. Every window gets a 0-20 score per genre from word choice and sentence shape; the entertainment points (0-25) are the mix-weighted sum. **Comedy is always graded** (setup + short punchline, retorts, absurd numbers, insults, laughter, swearing used for effect) and blended in 20% even when the mix has no comedy: a laugh travels in every genre. The judge prints the same genre scores on the finished clip.

**Backtest** before changing weights: `python3 bot/backtest.py words.json --style cinematic --truth 26.4-60.1,177.5-194.9` ranks approved clips; every approved clip should sit in the top 5 (2026-10-28: DIGGER reviewer picks 3/3, Mark Manson approved clip rank 4).

## What makes a podcast moment work (learned 2026-10-26)
- A real person and a number beat a concept: "his dad made him hit 2,500 balls a day" beats "shame drives compulsive behaviour".
- The speaker in close-up on the first word; the wide two-shot is for reactions, in a split, never the opener.
- A card or photo inside the window is worth a lot: the show's own graphic is the b-roll.
- 35-55 s. Shorter if the payoff is early.

## Files
- `bot/find_moments.py`, `bot/graphics_map.py`
- Per campaign: `/tmp/clipwork/<campaign>/` on the runner (candidates.md, gfx.json); the kept clips carry words.json and the reports
