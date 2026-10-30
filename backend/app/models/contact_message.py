"""
Contact message model for Smart Civic Guardian.
Stores messages submitted through the contact form in Supabase PostgreSQL.
"""

from datetime import datetime
from app.db import get_supabase_client


def create_message(user_id, name, email, department, message):
    """Inserts a contact message into Supabase."""
    client = get_supabase_client()
    payload = {
        "user_id": user_id,
        "name": name,
        "email": email,
        "department": department,
        "message": message,
    }
    res = client.table("contact_messages").insert(payload).execute()
    if res.data and len(res.data) > 0:
        return res.data[0]["id"]
    return None


def get_all_messages():
    """Retrieves all contact messages ordered newest first."""
    client = get_supabase_client()
    res = client.table("contact_messages").select("*").order("submitted_at", desc=True).execute()
    return res.data or []


def get_message_by_id(message_id):
    """Retrieves a single message by ID."""
    client = get_supabase_client()
    res = client.table("contact_messages").select("*").eq("id", message_id).execute()
    if res.data and len(res.data) > 0:
        return res.data[0]
    return None


def save_reply(message_id, reply_text):
    """Saves the admin's reply to a contact message."""
    client = get_supabase_client()
    now_iso = datetime.utcnow().isoformat()
    client.table("contact_messages").update({
        "reply_text": reply_text,
        "replied_at": now_iso,
    }).eq("id", message_id).execute()
