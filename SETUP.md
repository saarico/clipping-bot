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

## YouTube episodes from the cloud (secret YT_COOKIES)
YouTube refuses every GitHub machine ("Sign in to confirm you're not a bot"). Drive and Dropbox links need nothing.
For YouTube links the bot needs the cookies of a THROWAWAY Google account (never your own: never put your own
account's cookies anywhere). rico 2026-10-30: the home PC must play no part; everything runs in the cloud.
1. Make a new Google account just for this (any name, a phone may be asked once). Watch two or three YouTube
   videos signed in, so the account looks used.
2. In Chrome or Firefox, signed in to that account, open a private window, go to youtube.com, install the
   extension "Get cookies.txt LOCALLY", click it on youtube.com and export (Netscape format). Close the private
   window WITHOUT signing out (signing out invalidates the cookies).
3. GitHub -> repo -> Settings -> Secrets and variables -> Actions -> New repository secret: name `YT_COOKIES`,
   value = the whole text of the cookies.txt file. Paste it there only, never in chat.
4. Test: Actions -> probe -> Run workflow with any YouTube link; data/probe.log must end with "DOWNLOAD OK".
When the bot notes "YOUTUBE COOKIES NEEDED OR EXPIRED" in a SUMMARY or state, repeat steps 2-3 (cookies last weeks
to months). If Google locks the throwaway account, make another; nothing else is affected.

## Posting (what is automatic, what is your click)
- **YouTube Shorts / TikTok / Instagram**: each approved clip goes to ONE platform, chosen by what the clip is about
  (YouTube = business/money, Instagram = celebrity/drama, TikTok = entertainment; the SUMMARY shows it as "post on").
  The POST KIT doc in 3_APPROVED has that platform's title, description and tags; you upload with one click. Automatic posting needs each platform's app audit (weeks); it
  is a later step, and never a password typed anywhere but the platform's own screen.
- **Content Rewards**: no API. Paste the post link yourself.
