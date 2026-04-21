import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import settings


_security = HTTPBasic()


def require_basic_auth(
    credentials: HTTPBasicCredentials = Depends(_security),
) -> str:
    # constant-time compare so == doesn't leak the password via timing
    correct_user = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        settings.basic_auth_username.encode("utf-8"),
    )
    correct_pwd = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        settings.basic_auth_password.encode("utf-8"),
    )
    if not (correct_user and correct_pwd):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
