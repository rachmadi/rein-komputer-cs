# -*- coding: utf-8 -*-
"""
Modul Autentikasi Admin Bobby Computer (JWT & Password Hashing)
Melindungi seluruh endpoint manajemen katalog dari akses tanpa izin.
"""
from __future__ import annotations

import os
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "bobby_computer_super_secure_jwt_secret_key_2026")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
# Default password: admin123
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")

security_scheme = HTTPBearer(auto_error=False)

def _generate_salt() -> str:
    return secrets.token_hex(16)

def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or _generate_salt()
    pwd_bytes = password.encode("utf-8")
    salt_bytes = salt.encode("utf-8")
    h = hashlib.pbkdf2_hmac("sha256", pwd_bytes, salt_bytes, 100000)
    return f"{salt}${h.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if "$" not in hashed_password:
        return False
    salt, hash_hex = hashed_password.split("$", 1)
    recalculated = hash_password(plain_password, salt=salt).split("$", 1)[1]
    return hmac.compare_digest(hash_hex, recalculated)

# Inisialisasi hash default jika belum ada
if not ADMIN_PASSWORD_HASH:
    DEFAULT_ADMIN_HASH = hash_password("admin123", salt="bobby_fixed_salt_2026")
else:
    DEFAULT_ADMIN_HASH = ADMIN_PASSWORD_HASH

def authenticate_admin(username: str, password: str) -> bool:
    if username != ADMIN_USERNAME:
        return False
    return verify_password(password, DEFAULT_ADMIN_HASH)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> str:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Akses ditolak: Autentikasi admin diperlukan",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        if not username or username != ADMIN_USERNAME:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token tidak valid untuk user admin",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesi login telah kedaluwarsa. Silakan login kembali.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kredensial token tidak valid",
            headers={"WWW-Authenticate": "Bearer"},
        )
