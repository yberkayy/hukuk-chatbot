"""
Authentication Module
======================
Verifies NextAuth.js session tokens and provides user dependency for FastAPI.
Supports both JWT-based verification and a simple token-based approach
that works with NextAuth's session callback.
"""
import logging
from typing import Optional

from fastapi import Depends, HTTPException, Header

from app.config import settings
from app.database import upsert_user

logger = logging.getLogger(__name__)


import urllib.parse

async def get_current_user(
    x_user_id: Optional[str] = Header(None),
    x_user_email: Optional[str] = Header(None),
    x_user_name: Optional[str] = Header(None),
    x_user_image: Optional[str] = Header(None),
) -> dict:
    """
    Bypass authentication and always return a local default user.
    """
    local_user_id = "local_user"
    local_email = "local@user.com"
    local_name = "Local User"
    local_image = ""
    
    # Upsert user in database
    user = await upsert_user(
        user_id=local_user_id,
        email=local_email,
        name=local_name,
        image=local_image,
    )
    
    return {
        "id": local_user_id,
        "email": local_email,
        "name": local_name,
        "image": local_image,
    }


async def get_optional_user(
    x_user_id: Optional[str] = Header(None),
    x_user_email: Optional[str] = Header(None),
    x_user_name: Optional[str] = Header(None),
    x_user_image: Optional[str] = Header(None),
) -> Optional[dict]:
    """
    Always return the local default user.
    """
    return await get_current_user()
