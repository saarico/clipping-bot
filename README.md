# clipping-bot

Turns a creator's long video into short clips for paid clipping campaigns (Content Rewards), with
rico's Google Drive as the only place rico has to look. Runs on GitHub every 5 hours.

```
Drive: CLIPPING/
  0_START/<campaign>/        bot: folder + JOIN doc (link, pay, score) for each pick (financial scorecard, lane balance first)
                             you: join, drop the requirements (pdf/docx/doc) + episode.mp4 if asked   bot: BRIEF
                             (your own campaign: make the folder yourself and drop the requirements)
  1_CHECK/<campaign>/        bot: max 3 clips + SUMMARY (why these moments, scores, captions)
  2_REDO/<campaign>/         you: a Word doc with your critique                           bot: re-picks
  3_APPROVED/<campaign>/     you: drag the clip here                                      bot: POST KIT
```

| Step | Who | Where |
|---|---|---|
| Find campaigns | bot | `bot/campaign_scan.py`, `scorecards/financial.md` |
| Join (link in the JOIN doc), download requirements, drop in 0_START/<campaign>/ | rico | Drive |
| Read requirements, pick the video, get the file | bot | `bot/brief.py`, `bot/run.py` (yt-dlp, else asks for the mp4) |
| Transcribe the whole episode | bot | `bot/transcribe.py` (Whisper on CPU) |
| Pick max 3 moments | bot / reviewer | `bot/plan.py`, `scorecards/entertainment.md`, `campaigns/<c>/plan.json` |
| Cut, inspect, judge, retry | bot | `bot/render_clip.py` (YuNet face tracking, one 9:16 look), `bot/qa_check.py` (hard gates, `scorecards/acceptance.md`), `bot/judge_clip.py` (bar 80, `scorecards/judgment.md`), `bot/pipeline.py` grade-and-retry (re-edit once, then the next moment; clips that pass every gate at 75-79 go up marked UNDER THE BAR when nothing reaches 80) |
| Lane: one platform per clip | bot | `bot/lanes.py` (YouTube = business/money, Instagram = celebrity/drama, TikTok = entertainment), shown in the SUMMARY |
| Review | rico | 1_CHECK → 2_REDO or 3_APPROVED |
| Thumbnail (most clickable face, not at a shout; 2-6 words, one yellow; 4-frame options sheet; appended as the last frame for the Shorts/TikTok pickers) | bot | `bot/thumbnail.py` |
| Post kit (one platform, title, description, tags, thumbnail) | bot | `bot/post_kit.py`, `config/accounts.json` |
| Post, paste the link into Content Rewards | rico (one click from the POST KIT) | see SETUP.md |

Rules the bot follows: `RULES.md`. Every rule change with its date: `CHANGELOG.md`. Acceptance gates: `scorecards/acceptance.md`. rico's critiques land in `campaigns/<c>/critiques/` and the reviewer
applies them in the next `plan.json`. State per campaign: `campaigns/<c>/state.json`. Videos never enter git.

Run by hand: Actions → run → Run workflow (optionally one campaign folder name).
Local test of the cutting line without Drive: `python3 bot/pipeline.py <work dir> <episode.mp4> <brief.json>`.

## Grading profiles (per kind of footage)

`bot/profiles.py`: podcast, cinematic (trailers, scene clips), stream (gaming, live reactions), performance (music, concerts). The profile decides which QA checks are hard FAILs, the pace and length targets, and what counts as a strong moment (stakes words for podcasts, short quotable lines for trailers, hype words and loud seconds for streams). Set it in `plan.json` `brief_overrides.style`; otherwise the bot reads the brief, then the footage.

## Brand mode (silent product footage, parked: no ad campaigns)

Some campaigns (FOLD) hand out app demos instead of a talking episode. For those the reviewer writes
up to 3 short scripts in `campaigns/<c>/plan.json` under `brand_clips` (hook, script lines, which footage
file under each line). `bot/brand_mode.py` gives the script a voice (edge-tts, free, word-timed), lays
the footage under it (fit inside, blurred copy behind), adds the title band, word captions and the
campaign's disclosure line under the title, runs one QA pass (length, forbidden claims, brand named,
disclosure) and uploads to 1_CHECK like any other clip. Silent footage with no scripts yet is logged as
"needs scripts" and nothing is transcribed.
