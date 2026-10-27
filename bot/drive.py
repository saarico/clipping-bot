"""Google Drive for the bot. One OAuth token (rico's own account, scopes drive + youtube.upload),
stored as the GitHub secret GOOGLE_TOKEN_JSON. Nothing here ever sees a password.

Folder layout the bot expects (created on first run if missing):
  CLIPPING/
    CAMPAIGNS TO JOIN            (Google Doc, bot-written)
    <campaign>/0_START  1_CHECK  2_REDO  3_APPROVED
"""
import io
import json
import mimetypes
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

FOLDER = "application/vnd.google-apps.folder"
GDOC = "application/vnd.google-apps.document"
STAGES = ["0_START", "1_CHECK", "2_REDO", "3_APPROVED"]
_svc = None


def creds():
    raw = os.environ.get("GOOGLE_TOKEN_JSON") or Path(os.environ.get("GOOGLE_TOKEN_FILE", "token.json")).read_text()
    return Credentials.from_authorized_user_info(json.loads(raw))


def svc():
    global _svc
    if _svc is None:
        _svc = build("drive", "v3", credentials=creds(), cache_discovery=False)
    return _svc


def q(query, fields="files(id,name,mimeType,modifiedTime,size,parents)"):
    out, token = [], None
    while True:
        r = svc().files().list(q=query, fields="nextPageToken," + fields, pageToken=token, pageSize=200,
                               supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        out += r.get("files", [])
        token = r.get("nextPageToken")
        if not token:
            return out


def esc(s):
    return s.replace("\\", "\\\\").replace("'", "\\'")


def children(folder_id, mime=None):
    extra = f" and mimeType = '{mime}'" if mime else ""
    return q(f"'{folder_id}' in parents and trashed = false{extra}")


def find_folder(name, parent=None):
    p = f" and '{parent}' in parents" if parent else ""
    hits = q(f"name = '{esc(name)}' and mimeType = '{FOLDER}' and trashed = false{p}")
    return hits[0]["id"] if hits else None


def ensure_folder(name, parent=None):
    fid = find_folder(name, parent)
    if fid:
        return fid
    body = {"name": name, "mimeType": FOLDER}
    if parent:
        body["parents"] = [parent]
    return svc().files().create(body=body, fields="id", supportsAllDrives=True).execute()["id"]


def root():
    return ensure_folder(os.environ.get("CLIPPING_ROOT", "CLIPPING"))


def campaigns():
    """[(name, folder_id)] for every folder directly under CLIPPING."""
    return [(f["name"], f["id"]) for f in children(root(), FOLDER)]


def stages(campaign_id):
    return {s: ensure_folder(s, campaign_id) for s in STAGES}


def download(file_id, dest, mime=None):
    """Download a file. Google Docs are exported (default: plain text)."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    meta = svc().files().get(fileId=file_id, fields="mimeType,name", supportsAllDrives=True).execute()
    if meta["mimeType"].startswith("application/vnd.google-apps"):
        req = svc().files().export_media(fileId=file_id, mimeType=mime or "text/plain")
    else:
        req = svc().files().get_media(fileId=file_id, supportsAllDrives=True)
    with io.FileIO(dest, "wb") as fh:
        dl = MediaIoBaseDownload(fh, req, chunksize=32 * 1024 * 1024)
        done = False
        while not done:
            _, done = dl.next_chunk()
    return dest


def upload(path, folder_id, name=None, mime=None, replace=True):
    """Upload a local file into a folder; replaces a same-named file when replace=True."""
    path = Path(path)
    name = name or path.name
    mime = mime or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    media = MediaFileUpload(str(path), mimetype=mime, resumable=path.stat().st_size > 5 * 1024 * 1024)
    if replace:
        for f in q(f"name = '{esc(name)}' and '{folder_id}' in parents and trashed = false", "files(id)"):
            return svc().files().update(fileId=f["id"], media_body=media, fields="id", supportsAllDrives=True).execute()["id"]
    body = {"name": name, "parents": [folder_id]}
    return svc().files().create(body=body, media_body=media, fields="id", supportsAllDrives=True).execute()["id"]


def write_doc(name, text, folder_id):
    """Create or replace a Google Doc (from plain text) so rico can open it with one click."""
    tmp = Path("/tmp") / (name.replace("/", "_") + ".txt")
    tmp.write_text(text)
    media = MediaFileUpload(str(tmp), mimetype="text/plain")
    hits = q(f"name = '{esc(name)}' and '{folder_id}' in parents and mimeType = '{GDOC}' and trashed = false", "files(id)")
    if hits:
        return svc().files().update(fileId=hits[0]["id"], media_body=media, fields="id", supportsAllDrives=True).execute()["id"]
    body = {"name": name, "parents": [folder_id], "mimeType": GDOC}
    return svc().files().create(body=body, media_body=media, fields="id", supportsAllDrives=True).execute()["id"]


def move(file_id, from_id, to_id):
    svc().files().update(fileId=file_id, addParents=to_id, removeParents=from_id, fields="id", supportsAllDrives=True).execute()


def text_of(file_id, name):
    """Plain text of a requirements / critique file: Google Doc, .docx, .pdf, .txt, .md."""
    low = name.lower()
    local = Path("/tmp/drive_text") / name
    if low.endswith((".docx",)):
        download(file_id, local)
        import docx
        d = docx.Document(str(local))
        parts = [p.text for p in d.paragraphs]
        for t in d.tables:
            for row in t.rows:
                parts.append(" | ".join(c.text for c in row.cells))
        return "\n".join(parts)
    if low.endswith(".pdf"):
        download(file_id, local)
        import pdfplumber
        with pdfplumber.open(str(local)) as pdf:
            return "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    download(file_id, local.with_suffix(".txt"))  # Google Docs export to text; txt/md download as is
    return local.with_suffix(".txt").read_text(errors="replace")
