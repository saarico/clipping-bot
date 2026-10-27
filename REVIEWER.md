# The reviewer (Claude) — what it does between bot runs

The bot on GitHub is the muscle. The reviewer is Claude in the "SOCIAL MEDIA CLIPPING" project, woken
every 5 hours (offset from the bot), with Drive and this repo attached. It never renders; it writes files
the bot reads.

Per campaign under `campaigns/<c>/`:
1. Read `brief.json` (the campaign rules) and `words.json` (the whole transcript) and any
   `critiques/*.md` (rico's Word docs from 2_REDO, newest wins).
2. Apply `scorecards/entertainment.md` to the whole episode and pick the 3 moments. Check each against
   RULES.md and the brief (face in first N seconds, no ad reads, finishes the point).
3. Write `plan.json`: `{"why": "...", "clips": [render_clip spec, ...]}` (spec format in
   `bot/render_clip.py`'s docstring: parts, hook, hook_hi, emphasis, focus, callouts, overlays).
   Max 3 clips. After a critique: change only what rico flagged.
4. Commit and push `plan.json`; the next bot run renders it and refreshes 1_CHECK. To run the bot at
   once, trigger the workflow (Actions → run).
If the reviewer has not written a plan, the bot picks moments itself with the scorecard (weaker hooks,
no callouts) so a campaign never waits.
