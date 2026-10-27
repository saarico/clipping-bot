# One-time setup (rico, about 5 minutes)

The bot reaches your Google Drive through **rclone**, a free tool Google already recognises. No Google
Cloud project, no consent screen, no client files. You sign in once on Google's own page.

## 1. Install rclone (PowerShell)
```
winget install Rclone.Rclone
```
(or download from https://rclone.org/downloads/ and unzip). Close and reopen PowerShell.

## 2. Sign in once
```
rclone authorize "drive" > token.txt
```
A browser opens on Google's sign-in; approve ("Success!"). Open token.txt in Notepad: the block that
starts with `{"access_token":` and ends with `}` is the token.

## 3. Put it in GitHub
https://github.com/saarico/clipping-bot/settings/secrets/actions/new
- Name: `RCLONE_TOKEN`
- Secret: the block from step 2
Then delete token.txt. Never paste the block in a chat. If it ever leaks, run step 2 again and replace
the secret; the old token can be revoked at https://myaccount.google.com/permissions (remove "rclone").

## 4. First run
Actions → **run** → Run workflow. The bot creates `CAMPAIGNS TO JOIN` and `CAMPAIGN LINKS` in your
CLIPPING folder. The bot creates `CLIPPING/0_START/<campaign>/` with a JOIN doc for each campaign it recommends; drop the requirements (and episode.mp4 if assigned) in that folder. For a campaign you found yourself, make the folder and drop the requirements.

## Posting (what is automatic, what is your click)
- **YouTube Shorts / TikTok / Instagram**: the POST KIT doc in 3_APPROVED has the title, description
  and tags; you upload with one click. Automatic posting needs each platform's app audit (weeks); it
  is a later step, and never a password typed anywhere but the platform's own screen.
- **Content Rewards**: no API. Paste the post link yourself.
