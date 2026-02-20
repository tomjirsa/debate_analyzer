"""HTTP Basic Auth for admin routes."""

import os
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()


def get_admin_credentials(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
) -> HTTPBasicCredentials:
    """
    Verify HTTP Basic credentials against env ADMIN_USERNAME and ADMIN_PASSWORD.
    Raises 401 if missing or invalid.
    """
    username = os.environ.get("ADMIN_USERNAME", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "").strip()
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin auth not configured (ADMIN_USERNAME/ADMIN_PASSWORD)",
        )
    if credentials.username != username or credentials.password != password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials
