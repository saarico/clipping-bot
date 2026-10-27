# clipping-bot

Turns a creator's long video into short clips for paid clipping campaigns (Content Rewards), with
rico's Google Drive as the only place rico has to look. Runs on GitHub every 5 hours.

```
Drive: CLIPPING/
  CAMPAIGNS TO JOIN          bot: scored list with links (financial scorecard, lane balance first)
  CAMPAIGN LINKS             you: paste campaign links here when the scan is blocked
  <campaign>/
    0_START/                 you: requirements (pdf/docx/doc) + episode.mp4 if asked     bot: BRIEF
    1_CHECK/                 bot: max 3 clips + SUMMARY (why these moments, scores, captions)
    2_REDO/                  you: a Word doc with your critique                           bot: re-picks
    3_APPROVED/              you: drag the clip here                                      bot: POST KIT
```

| Step | Who | Where |
|---|---|---|
| Find campaigns | bot | `bot/campaign_scan.py`, `scorecards/financial.md` |
| Join, download requirements, drop in 0_START | rico | Drive |
| Read requirements, pick the video, get the file | bot | `bot/brief.py`, `bot/run.py` (yt-dlp, else asks for the mp4) |
| Transcribe the whole episode | bot | `bot/transcribe.py` (Whisper on CPU) |
| Pick max 3 moments | bot / reviewer | `bot/plan.py`, `scorecards/entertainment.md`, `campaigns/<c>/plan.json` |
| Cut, QA, judge | bot | `bot/render_clip.py`, `bot/qa_check.py`, `bot/judge_clip.py`, `scorecards/judgment.md` |
| Review | rico | 1_CHECK → 2_REDO or 3_APPROVED |
| Post kit (title, description, tags) | bot | `bot/post_kit.py`, `config/accounts.json` |
| Post, paste the link into Content Rewards | rico (until the platform audits pass) | see SETUP.md |

Rules the bot follows: `RULES.md`. rico's critiques land in `campaigns/<c>/critiques/` and the reviewer
applies them in the next `plan.json`. State per campaign: `campaigns/<c>/state.json`. Videos never enter git.

Run by hand: Actions → run → Run workflow (optionally one campaign folder name).
Local test of the cutting line without Drive: `python3 bot/pipeline.py <work dir> <episode.mp4> <brief.json>`.
