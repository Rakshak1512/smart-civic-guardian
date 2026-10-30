"""
Notification model for Smart Civic Guardian.
Stores and retrieves in-app notifications in Supabase PostgreSQL.
"""

from app.db import get_supabase_client


def create_notification(user_id, message, complaint_id=None):
    """Inserts a notification for a user."""
    client = get_supabase_client()
    payload = {
        "user_id": user_id,
        "message": message,
        "is_read": 0,
    }
    if complaint_id:
        payload["complaint_id"] = complaint_id
    res = client.table("notifications").insert(payload).execute()
    if res.data and len(res.data) > 0:
        return res.data[0]["id"]
    return None


def get_notifications_for_user(user_id, limit=50, category=None):
    """Retrieves notifications for a user, newest first."""
    client = get_supabase_client()
    query = client.table("notifications").select("*, complaints(category)").eq("user_id", user_id).order("created_at", desc=True).limit(limit)
    res = query.execute()
    items = []
    for row in res.data or []:
        complaint = row.get("complaints") or {}
        comp_cat = complaint.get("category")
        if category and comp_cat and comp_cat != category:
            continue
        items.append(row)
    return items


def get_unread_count(user_id, category=None):
    """Counts unread notifications for a user."""
    client = get_supabase_client()
    res = client.table("notifications").select("id, complaints(category)", count="exact").eq("user_id", user_id).eq("is_read", 0).execute()
    if not category:
        return res.count or 0
    count = 0
    for row in res.data or []:
        complaint = row.get("complaints") or {}
        if complaint.get("category") == category or not row.get("complaint_id"):
            count += 1
    return count


def mark_all_read(user_id):
    """Marks all notifications as read for a user."""
    client = get_supabase_client()
    client.table("notifications").update({"is_read": 1}).eq("user_id", user_id).execute()


def mark_one_read(notification_id, user_id):
    """Marks a single notification as read."""
    client = get_supabase_client()
    client.table("notifications").update({"is_read": 1}).eq("id", notification_id).eq("user_id", user_id).execute()
