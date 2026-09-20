import hashlib, secrets, re
from ..extensions import bcrypt
def hash_token(token): return hashlib.sha256(token.encode()).hexdigest()
def generate_secure_token(): return secrets.token_urlsafe(48)
def hash_password(password): return bcrypt.generate_password_hash(password).decode()
def verify_password(password_hash, password): return bcrypt.check_password_hash(password_hash, password)
def validate_password(password):
    if not 12 <= len(password) <= 128: raise ValueError("Password must contain 12-128 characters.")
    if not re.search(r"[A-Z]", password): raise ValueError("Password needs an uppercase letter.")
    if not re.search(r"[a-z]", password): raise ValueError("Password needs a lowercase letter.")
    if not re.search(r"\d", password): raise ValueError("Password needs a number.")
    if not re.search(r"[^A-Za-z0-9]", password): raise ValueError("Password needs a special character.")
    return True
