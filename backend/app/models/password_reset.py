"""
Password reset model for Smart Civic Guardian.
Stores reset tokens and OTP hashes in Supabase PostgreSQL.
"""

import secrets
from datetime import datetime, timedelta
from app.db import get_supabase_client


def create_reset_token(user_id, token=None, expires_minutes=60):
    """Creates a reset token record in Supabase PostgreSQL."""
    client = get_supabase_client()
    if not token:
        token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(minutes=expires_minutes)).isoformat()
    
    # Invalidate previous unused tokens for this user
    client.table("password_resets").update({"used": 1}).eq("user_id", user_id).eq("used", 0).execute()
    
    payload = {
        "user_id": user_id,
        "token": token,
        "expires_at": expires_at,
        "used": 0,
    }
    client.table("password_resets").insert(payload).execute()
    return token


def get_valid_reset(token):
    """Retrieves an active, unused token that has not expired."""
    client = get_supabase_client()
    res = client.table("password_resets").select("*").eq("token", token).eq("used", 0).execute()
    if not res.data or len(res.data) == 0:
        return None
    row = res.data[0]
    exp = row.get("expires_at")
    if exp:
        # Check expiry
        try:
            exp_clean = exp.replace("Z", "+00:00")
            exp_dt = datetime.fromisoformat(exp_clean)
            # Remove tzinfo for UTC comparison if needed
            if exp_dt.tzinfo is not None:
                from datetime import timezone
                if exp_dt < datetime.now(timezone.utc):
                    return None
            else:
                if exp_dt < datetime.utcnow():
                    return None
        except Exception:
            pass
    return row


def mark_reset_used(token):
    """Marks a token as used."""
    client = get_supabase_client()
    client.table("password_resets").update({"used": 1}).eq("token", token).execute()
