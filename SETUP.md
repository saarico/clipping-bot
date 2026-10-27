# One-time setup (rico, about 15 minutes)

The bot needs one Google sign-in (Drive to read/write your folders, YouTube to upload later). It is
the official Google consent screen; no password is typed anywhere but Google's own page.

## 1. Google Cloud project (free)
1. Open https://console.cloud.google.com/projectcreate → name `clipping-bot` → Create.
2. APIs & Services → Library → enable **Google Drive API** and **YouTube Data API v3**.
3. APIs & Services → OAuth consent screen → External → app name `clipping-bot`, your email → Save.
   Under **Audience → Test users** add your own Gmail address.
4. APIs & Services → Credentials → Create credentials → **OAuth client ID** → type **Desktop app** →
   Create → **Download JSON** → save it as `client_secret.json`.

## 2. Sign in once and make the token
On any computer with Python 3 (or a GitHub Codespace on this repo):
```
pip install google-auth-oauthlib
python bot/auth_google.py client_secret.json
```
A browser opens, you approve Drive + YouTube upload, and `token.json` appears.

## 3. Put the token in GitHub
Repo → Settings → Secrets and variables → Actions → New repository secret:
- Name: `GOOGLE_TOKEN_JSON`
- Value: the whole content of `token.json`
Then delete `token.json` and `client_secret.json` from your computer.

## 4. First run
Actions → **run** → Run workflow. It creates `CAMPAIGNS TO JOIN` and `CAMPAIGN LINKS` in your
CLIPPING folder. Make a folder per campaign under CLIPPING, drop the requirements in `0_START`, done.

## Posting (what is automatic, what is your click)
- **Instagram Reels**: can be automatic through the official API once the account is a Creator/Business
  account linked to a Facebook Page. Not wired yet; the POST KIT covers it until then.
- **YouTube Shorts**: the API works today, but Google keeps API uploads **private** until it audits the
  app (takes weeks). Until then: POST KIT → upload with one click.
- **TikTok**: API uploads are private-only without an audit. POST KIT → one click.
- **Content Rewards**: no API. Paste the post link yourself.
