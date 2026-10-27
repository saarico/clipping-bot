"""One-time sign-in, run by rico on any computer with Python (or in a GitHub Codespace):

  pip install google-auth-oauthlib
  python bot/auth_google.py client_secret.json

It opens the official Google consent screen (Drive + YouTube upload), then writes token.json.
Paste the CONTENT of token.json into the GitHub secret GOOGLE_TOKEN_JSON. Never paste it in a chat.
"""
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/youtube.upload",
]

if __name__ == "__main__":
    secret = sys.argv[1] if len(sys.argv) > 1 else "client_secret.json"
    flow = InstalledAppFlow.from_client_secrets_file(secret, SCOPES)
    try:
        creds = flow.run_local_server(port=0, open_browser=True)
    except Exception:
        creds = flow.run_console()
    with open("token.json", "w") as f:
        f.write(creds.to_json())
    print("token.json written. Put its content in the GitHub secret GOOGLE_TOKEN_JSON, then delete the file.")
    print(json.dumps({"scopes": creds.scopes}))
