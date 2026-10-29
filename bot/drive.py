"""rico's Google Drive, through rclone. No Google Cloud project: rico runs `rclone authorize "drive"`
once and puts the printed token in the GitHub secret RCLONE_TOKEN (SETUP.md).

Everything is a PATH under the CLIPPING folder, never a file id:
  CLIPPING/<campaign>/0_START  1_CHECK  2_REDO  3_APPROVED
Google Docs are read as text and written from text (rclone's import/export formats).

Backends:  rclone (production, env RCLONE_TOKEN or an existing rclone remote "gdrive")
           local  (tests: env CLIPPING_LOCAL=/some/dir acts as the Drive)
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

STAGES = ["0_START", "1_CHECK", "2_REDO", "3_APPROVED"]
ROOT_NAME = os.environ.get("CLIPPING_ROOT", "CLIPPING")
GDOC = "application/vnd.google-apps.document"
TEXT_EXT = (".txt", ".md")


class Local:
    """A directory standing in for Drive (tests). Google Docs are plain .txt files."""

    def __init__(self, base):
        self.base = Path(base)

    def _p(self, path):
        return self.base / path

    def ls(self, path):
        d = self._p(path)
        if not d.exists():
            return []
        out = []
        for e in sorted(d.iterdir()):
            out.append({"Name": e.name, "Path": f"{path}/{e.name}", "IsDir": e.is_dir(), "Size": e.stat().st_size,
                        "ModTime": e.stat().st_mtime,
                        "MimeType": "inode/directory" if e.is_dir() else ("text/plain" if e.suffix == ".txt" else "application/octet-stream")})
        return out

    def mkdir(self, path):
        self._p(path).mkdir(parents=True, exist_ok=True)

    def download(self, path, dest):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(self._p(path), dest)
        return Path(dest)

    def upload(self, local, path):
        self._p(path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(local, self._p(path))

    def write_doc(self, path, text):
        self._p(path + ".txt").parent.mkdir(parents=True, exist_ok=True)
        self._p(path + ".txt").write_text(text)

    def move(self, src, dst):
        self._p(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(self._p(src), self._p(dst))


class Rclone:
    def __init__(self):
        self.remote = os.environ.get("RCLONE_REMOTE", "gdrive")
        conf = Path(os.environ.get("RCLONE_CONFIG", str(Path.home() / ".config/rclone/rclone.conf")))
        tok = os.environ.get("RCLONE_TOKEN", "")
        if "{" in tok and not conf.exists():
            tok = tok[tok.index("{"):tok.rindex("}") + 1]   # the secret may be the whole `rclone authorize` output
            json.loads(tok)
            conf.parent.mkdir(parents=True, exist_ok=True)
            conf.write_text(f"[{self.remote}]\ntype = drive\nscope = drive\ntoken = {tok}\n")
        self.flags = ["--drive-export-formats", "txt", "--drive-import-formats", "txt", "-q"]

    def _r(self, path):
        return f"{self.remote}:{path}"

    def run(self, *args, check=True, timeout=1800):
        r = subprocess.run(["rclone", *args, *self.flags], capture_output=True, text=True, timeout=timeout)
        if check and r.returncode != 0:
            raise RuntimeError(f"rclone {args[0]} failed: {r.stderr.strip()[-400:]}")
        return r

    def ls(self, path):
        r = self.run("lsjson", self._r(path), check=False)
        if r.returncode != 0:
            # a folder that is not there is an empty list; anything else (token expired, quota, network) must be seen,
            # or a run reads every stage as empty and quietly does nothing (2026-10-29 audit)
            if r.returncode == 3 or "directory not found" in r.stderr or "not found" in r.stderr:
                return []
            raise RuntimeError(f"rclone lsjson {path} failed ({r.returncode}): {r.stderr.strip()[-300:]}")
        out = []
        for e in json.loads(r.stdout or "[]"):
            e["Path"] = f"{path}/{e['Name']}"
            out.append(e)
        return out

    def mkdir(self, path):
        self.run("mkdir", self._r(path))

    def download(self, path, dest):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        self.run("copyto", self._r(path), str(dest), timeout=7200)
        return Path(dest)

    def upload(self, local, path):
        self.run("copyto", str(local), self._r(path), timeout=7200)

    def write_doc(self, path, text):
        """A Google Doc: upload NAME.txt with import-formats txt; Drive converts it to a Doc named NAME."""
        tmp = Path("/tmp/drive_docs") / (Path(path).name + ".txt")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text)
        self.run("copyto", str(tmp), self._r(path + ".txt"))

    def move(self, src, dst):
        self.run("moveto", self._r(src), self._r(dst))


_be = None


def be():
    global _be
    if _be is None:
        _be = Local(os.environ["CLIPPING_LOCAL"]) if os.environ.get("CLIPPING_LOCAL") else Rclone()
    return _be


_root_checked = False


def root():
    """CLIPPING/ with the four numbered stage folders directly under it (checked once per process)."""
    global _root_checked
    if not _root_checked:
        be().mkdir(ROOT_NAME)
        have = {e["Name"] for e in be().ls(ROOT_NAME) if e.get("IsDir")}
        for s in STAGES:
            if s not in have:
                be().mkdir(f"{ROOT_NAME}/{s}")
        _root_checked = True
    return ROOT_NAME


def campaigns():
    """[(name, name)] for every campaign folder found inside any stage folder.
    Layout: CLIPPING/<stage>/<campaign>/ (rico makes the campaign folder inside 0_START)."""
    r = root()
    names = []
    for s in STAGES:
        for e in be().ls(f"{r}/{s}"):
            if e.get("IsDir") and e["Name"] not in names:
                names.append(e["Name"])
    return [(n, n) for n in names]


def stages(campaign, create=True):
    """{stage: 'CLIPPING/<stage>/<campaign>'}. With create, the campaign folder is made in every stage
    (only done once a campaign has requirements, so 'to join' folders stay a single folder in 0_START)."""
    r = root()
    out = {}
    for s in STAGES:
        if create:
            have = {e["Name"] for e in be().ls(f"{r}/{s}") if e.get("IsDir")}
            if campaign not in have:
                be().mkdir(f"{r}/{s}/{campaign}")
        out[s] = f"{r}/{s}/{campaign}"
    return out


def files(path, exts=None):
    """Files in a folder. Google Docs show up as NAME.txt (rclone export) with MimeType GDOC."""
    out = []
    for e in be().ls(path):
        if e.get("IsDir"):
            continue
        name = e["Name"]
        e["is_doc"] = e.get("MimeType") == GDOC or name.lower().endswith(TEXT_EXT)
        if exts is None or name.lower().endswith(tuple(exts)) or (e["is_doc"] and ".txt" in exts):
            out.append(e)
    return out


def download(path, dest):
    return be().download(path, dest)


def upload(local, folder, name=None):
    be().upload(local, f"{folder}/{name or Path(local).name}")


def write_doc(name, text, folder):
    be().write_doc(f"{folder}/{name}", text)


def move(src, dst):
    be().move(src, dst)


def text_of(path, name):
    """Plain text of a requirements / critique file: Google Doc (exported .txt), .docx, .pdf, .txt, .md."""
    low = name.lower()
    local = Path("/tmp/drive_text") / name
    download(path, local)
    if low.endswith(".docx"):
        import docx
        d = docx.Document(str(local))
        parts = [p.text for p in d.paragraphs]
        for t in d.tables:
            for row in t.rows:
                parts.append(" | ".join(c.text for c in row.cells))
        return "\n".join(parts)
    if low.endswith(".pdf"):
        import pdfplumber
        with pdfplumber.open(str(local)) as pdf:
            return "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    return local.read_text(errors="replace")


def drop(campaign):
    """Move every stage folder of a dropped campaign into CLIPPING/_trash/<stage>_<campaign> (nothing is deleted)."""
    r = root()
    moved = []
    for s in STAGES:
        have = {e["Name"] for e in be().ls(f"{r}/{s}") if e.get("IsDir")}
        if campaign in have:
            be().move(f"{r}/{s}/{campaign}", f"{r}/_trash/{s}_{campaign}")
            moved.append(s)
    return moved
