import hashlib, mimetypes, secrets
from pathlib import Path
from werkzeug.utils import secure_filename
def extension(name): return Path(name).suffix.lower().lstrip(".")
def validate_upload(name, allowed):
    ext = extension(name)
    if ext not in allowed: raise ValueError("File type is not allowed.")
    return ext
def sha256_file(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()
def private_filename(ext): return f"{secrets.token_hex(24)}.{ext}"
def safe_org_path(root, org_id):
    p=(Path(root)/str(org_id)).resolve(); p.mkdir(parents=True,exist_ok=True); return p
def detect_mime(path): return mimetypes.guess_type(str(path))[0] or "application/octet-stream"
