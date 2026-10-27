# Judgment scorecard: is this clip good enough for rico

Run by bot/judge_clip.py (machine, 0-100) on every finished clip; the reviewer (Claude) reads captions.txt and the QA sheet blind when it plans a campaign. Bar for 1_CHECK: QA no FAIL and machine >= 70. Under the bar: the next moment is cut instead; no re-cut loops (rico, 2026-10-27).


rico, 2026-10-26: "Are we grading these clips and having a bot grade on likeness and entertainment and interest?" From now on, yes, every clip, before rico sees it. Two halves, both written into `judge_report.md` in the clip folder.

## Part 1: the machine (`bot/judge_clip.py`)
Measures what a scroller feels: hook (first 2.5 s names who/what, no pointer words), pace (words per second, silences, filler), visual variety (longest stretch without a change, share of cards/b-roll, punch-ins), framing (face centred, no letterbox, no micro-segments), story (stakes words, contrast or question, finished ending, no podcast back-references), length. Score out of 100.

## Part 2: the judge agent (blind read)
A separate Claude agent that did not make the cut. It gets only: `captions.txt`, `qa_sheet.png`, the machine report, and this rubric. It never sees the spec or the editor's reasoning. It scores:

| Area | /pts | The question it answers |
|---|---|---|
| Stop power | 25 | Reading only the title and the first spoken line: would a stranger stop scrolling? Is there a name, a number, a claim or a question in the first 2 seconds? |
| Stakes | 20 | Does a normal person (not a marketer, not a podcast fan) care? Money, a famous name, a failure, a surprise, a secret, a strong feeling. Shop talk and "we discussed this in another episode" score 0-5. |
| Payoff | 15 | Does the clip deliver what the title promised, and does it end on a finished thought that lands? |
| Clarity | 10 | Does it make sense with zero context: no "this", "that", "he" before a name, no reference to the episode? |
| Pace | 10 | No dead air, no rambling, cuts on the beat; the speaker gets to the point. |
| Visual life | 10 | A reason to keep the eyes on screen every few seconds: cards, b-roll, punch-ins, a reaction shot. From qa_sheet.png. |
| Framing | 10 | Speaker centred, true 9:16 throughout, no empty-room frames, text off faces. From qa_sheet.png. |

The agent writes 2-3 sentences of verdict in plain words ("boring because...", "would stop because...") plus one concrete fix if under the bar.

## The bar
- **Send to rico:** judge agent 75+ AND machine 70+ AND qa_check PASS AND thumbnail PASS.
- **Under the bar:** re-cut (new moment, new opener, more b-roll), do not send. Two re-cuts without passing = drop the moment.
- rico's own review is still the last word; the judge's job is that rico never again sees a clip that is off centre, boring or confusing.

## How to run it
```
python3 bot/qa_check.py <folder> --source <episode>
python3 bot/judge_clip.py <folder>
# then spawn the judge agent with the prompt in bot/judge_prompt.txt and the folder path; it appends Part 2
```
