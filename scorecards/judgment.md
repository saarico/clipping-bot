# Judgment scorecard: is this clip good enough for rico

Run by bot/judge_clip.py (machine, 0-100) on every finished clip; the reviewer (Claude) reads captions.txt and the QA sheet blind when it plans a campaign. Bar for 1_CHECK: QA no FAIL and machine >= 70. Under the bar: the next moment is cut instead; no re-cut loops (rico, 2026-10-27).


rico, 2026-10-26: "Are we grading these clips and having a bot grade on likeness and entertainment and interest?" From now on, yes, every clip, before rico sees it. Two halves, both written into `judge_report.md` in the clip folder.

## Part 1: the machine (`bot/judge_clip.py`)
Measures what a scroller feels, out of 100 (rebalanced 2026-10-28): hook 20 (first 2.5 s names who/what, no pointer words), pace 10 (words per second inside the media profile's band, silences, filler), variety 15 (longest stretch without a visual change, cards/b-roll, punch-ins), framing 10 (face centred, no letterbox, no micro-segments, no footage text cut off at the edge), story 10 (stakes words, contrast or question, finished ending, no podcast back-references), **entertainment 10** (bot/genres.py: the campaign's genre mix scored on what is actually said), **comedy 5** (always graded: setup + punch, retorts, absurd numbers, insults, laughter), **captions 10** (read like a person: 2-6 words per caption, nothing flashing, numbers whole, no unknown words, no cut-off fragments, swearing masked), length 10. The report prints the media profile and the genre scores so the reviewer sees why.

## Part 1b: the audience read (`bot/engage.py`, 0-100, bar 70, hard gates)
The story format as a stranger hears it (RULES 41 and the Story structure section): hook line said in the first 6 s,
who/what said in the first 10 s, why/how and progression after the hook, a last line that lands, no flat stretches,
clear speech. It runs on the candidate's words before rendering (the pitch rejects), when the cut's edges are chosen
(plan.refine picks the window with the best read) and on the finished clip (engage_report.md). A gate failure counts
like a QA FAIL. 2026-10-31: rico's verdict on the Higgsfield clips ("rely on the title... yap for the first few
seconds... hook, 5 Ws and progression weak") made the hook line, who/what and payoff hard gates.

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

## Weights per kind of content (board-approved 2026-10-31)
The machine areas above are each measured on their own scale (plus **sound /10** from the QA Audio row), then weighted
by the clip's content profile (`bot/profiles.WEIGHTS`, total 100):

| Area | podcast | talker | stream | cinematic | performance | serious | edit |
|---|---|---|---|---|---|---|---|
| hook | 20 | 25 | 20 | 20 | 15 | 20 | 20 |
| story | 20 | 20 | 10 | 15 | 10 | 25 | 10 |
| entertainment | 10 | 10 | 15 | 10 | 10 | 5 | 10 |
| comedy | 5 | 5 | 5 | 5 | 5 | 0 | 5 |
| framing | 5 | 5 | 8 | 10 | 12 | 5 | 10 |
| variety | 5 | 5 | 7 | 10 | 13 | 5 | 15 |
| pace | 10 | 10 | 15 | 10 | 15 | 10 | 15 |
| captions | 10 | 10 | 5 | 5 | 5 | 15 | 0 |
| sound | 5 | 5 | 10 | 10 | 10 | 5 | 10 |
| length | 10 | 5 | 5 | 5 | 5 | 10 | 5 |

Minimum per area: an area worth 10+ points that scores under half holds the clip under the bar (79), whatever the total.
The Text & layout inspector (`bot/studio.layout_check`) does the same on a layout failure. Starting weights are the
board's judgement; the Analyst (bot/analyst.py, release 4) nudges them once 20+ posts of a content type have 7-day
views in data/posts.csv: +2 on the two areas that track views best, -2 on the two that track worst, never more than 6
from this table, written to data/weights_tuned.json.
