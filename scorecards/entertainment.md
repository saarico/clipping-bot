# Entertainment scorecard: which moments of the episode get cut

Run by bot/find_moments.py over the whole transcript (every 20-60 s window), used by bot/plan.py when no reviewer plan exists. The reviewer (Claude) reads the top candidates in full and writes campaigns/<c>/plan.json with the 3 picks, hooks, callouts and the reasoning that goes into SUMMARY.


rico, 2026-10-26: "Are you able to read the entire video and judge and create a judgement and entertainment bot to find the best entertainment clip to make?" This is that process. It replaces "skim the transcript and pick the first good story".

## Steps
1. **Transcribe the whole episode** (OpusClip AI Producer, pieces of 30 min) into `words.json`.
2. **Map the show's graphics** with `bot/graphics_map.py <episode.mp4> gfx.json`: every card, photo and bottom strip with its time and box. These are our only b-roll (the campaign forbids outside material), so moments that have one score higher and the boxes go straight into the spec.
3. **Score every window** with `bot/find_moments.py words.json --graphics gfx.json`: all 20-60 s stretches that start and end on a sentence, scored for stakes (money, fame, failure, surprise, emotion, numbers), shape (question + answer, story markers, contrast, reactions), clarity of the first line, pace, visuals, payoff and length. Podcast back-references ("we talked about this in the shame episode") are penalised hard: a stranger is lost.
4. **Read the top 15 in full** (`candidates.md`), as a stranger. Keep only moments with a stake a normal person feels and a payoff that lands. Write the title first: if no 10-word title makes someone stop, the moment is out.
5. **Cut, then judge** (JUDGE.md). Only clips over the bar go to rico.

## What makes a Solved moment work (learned 2026-10-26)
- A real person and a number beat a concept: "Agassi's dad: 2,500 balls a day" beats "shame drives compulsive behaviour".
- Mark in close-up on the first word; the wide two-shot is for reactions, in a split, never the opener.
- A card or photo inside the window is worth a lot: the show's own graphic is the b-roll.
- 35-55 s. Shorter if the payoff is early.

## Files
- `bot/find_moments.py`, `bot/graphics_map.py`
- Per campaign: `SYSTEM/CAMPAIGNS/<campaign>/finder/<episode>_candidates.md` and `_gfx.json`
