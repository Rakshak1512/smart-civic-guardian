"""
Issue (complaint) model for Smart Civic Guardian.
Handles all database operations related to civic complaints directly
on Supabase PostgreSQL.
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from app.db import get_supabase_client


def _flatten_complaint(row):
    """Formats a Supabase complaint record with joined user and assignee fields."""
    if not row:
        return None
    data = dict(row)
    user_info = data.pop("users", None) or {}
    assignee_info = data.pop("assignee", None) or {}

    data["citizen_name"] = user_info.get("name") or "Anonymous Citizen"
    data["citizen_email"] = user_info.get("email") or ""
    data["citizen_phone"] = user_info.get("phone") or ""
    data["assignee_name"] = assignee_info.get("name") or "Unassigned"
    data["assigned_name"] = data["assignee_name"]
    return data


def create_complaint(data):
    """Inserts a new complaint into Supabase PostgreSQL."""
    client = get_supabase_client()
    payload = {
        "user_id": data["user_id"],
        "category": data["category"],
        "ai_detected_category": data.get("ai_detected_category"),
        "ai_confidence": data.get("ai_confidence"),
        "description": data["description"],
        "photo_path": data.get("photo_path"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "location_name": data.get("location_name"),
        "priority": data.get("priority", "Medium"),
        "status": "Pending",
        "duplicate_of": data.get("duplicate_of"),
        "duplicate_group": data.get("duplicate_group"),
        "support_count": data.get("support_count", 1),
    }
    res = client.table("complaints").insert(payload).execute()
    if res.data and len(res.data) > 0:
        return res.data[0]["id"]
    return None


def get_complaint_by_id(complaint_id):
    """Retrieves a single complaint with citizen and assignee details."""
    client = get_supabase_client()
    res = (
        client.table("complaints")
        .select("*, users!complaints_user_id_fkey(name, email, phone), assignee:users!complaints_assigned_to_fkey(name)")
        .eq("id", complaint_id)
        .execute()
    )
    if res.data and len(res.data) > 0:
        return _flatten_complaint(res.data[0])
    return None


def get_complaints_by_user(user_id):
    """Retrieves all complaints submitted by a specific citizen."""
    client = get_supabase_client()
    res = (
        client.table("complaints")
        .select("*, users!complaints_user_id_fkey(name, email, phone), assignee:users!complaints_assigned_to_fkey(name)")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [_flatten_complaint(r) for r in (res.data or [])]


def get_all_complaints(filters=None):
    """Retrieves all complaints with optional filtering."""
    client = get_supabase_client()
    query = (
        client.table("complaints")
        .select("*, users!complaints_user_id_fkey(name, email, phone), assignee:users!complaints_assigned_to_fkey(name)")
    )

    if filters:
        if filters.get("status"):
            query = query.eq("status", filters["status"])
        if filters.get("category"):
            query = query.eq("category", filters["category"])
        if filters.get("priority"):
            query = query.eq("priority", filters["priority"])

    query = query.order("created_at", desc=True)
    res = query.execute()
    items = [_flatten_complaint(r) for r in (res.data or [])]

    # In-memory search filter if text provided
    if filters and filters.get("search"):
        term = str(filters["search"]).strip().lower()
        items = [
            i for i in items
            if term in (i.get("description") or "").lower()
            or term in (i.get("location_name") or "").lower()
            or term in (i.get("category") or "").lower()
        ]

    return items


def get_recent_complaints_for_duplicate_check(category, days=30):
    """Retrieves recent complaints in a category for duplicate detection."""
    client = get_supabase_client()
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    res = (
        client.table("complaints")
        .select("*")
        .eq("category", category)
        .gte("created_at", cutoff)
        .is_("duplicate_of", "null")
        .execute()
    )
    return res.data or []


def update_status(complaint_id, status, resolution_notes=None, resolved_photo_path=None, assigned_to=None):
    """Updates complaint status, notes, assignee, and resolved timestamp in Supabase."""
    client = get_supabase_client()
    now_iso = datetime.utcnow().isoformat()
    payload = {
        "status": status,
        "updated_at": now_iso,
    }
    if resolution_notes is not None:
        payload["resolution_notes"] = resolution_notes
    if resolved_photo_path is not None:
        payload["resolved_photo_path"] = resolved_photo_path
    if assigned_to is not None:
        payload["assigned_to"] = assigned_to
    if status == "Resolved":
        payload["resolved_at"] = now_iso

    client.table("complaints").update(payload).eq("id", complaint_id).execute()


def increment_support_count(complaint_id):
    """Increments the community support count for a complaint."""
    client = get_supabase_client()
    res = client.table("complaints").select("support_count").eq("id", complaint_id).execute()
    if res.data:
        curr = res.data[0].get("support_count") or 1
        client.table("complaints").update({"support_count": curr + 1}).eq("id", complaint_id).execute()


def mark_as_duplicate(complaint_id, original_id, duplicate_group):
    """Marks a complaint as a duplicate of an existing complaint."""
    client = get_supabase_client()
    client.table("complaints").update({
        "duplicate_of": original_id,
        "duplicate_group": duplicate_group,
    }).eq("id", complaint_id).execute()


def get_stats(user_role=None, user_id=None, category=None):
    """Calculates summary statistics for complaints."""
    client = get_supabase_client()
    query = client.table("complaints").select("id, status, priority, category, user_id")
    if user_role == "citizen" and user_id:
        query = query.eq("user_id", user_id)
    if category:
        query = query.eq("category", category)

    res = query.execute()
    rows = res.data or []

    total = len(rows)
    pending = sum(1 for r in rows if r.get("status") == "Pending")
    in_progress = sum(1 for r in rows if r.get("status") == "In Progress")
    resolved = sum(1 for r in rows if r.get("status") == "Resolved")
    high_priority = sum(1 for r in rows if r.get("priority") == "High")

    return {
        "total": total,
        "pending": pending,
        "in_progress": in_progress,
        "resolved": resolved,
        "high_priority": high_priority,
    }


def get_category_breakdown(category=None):
    """Returns complaint counts grouped by category."""
    client = get_supabase_client()
    query = client.table("complaints").select("category")
    if category:
        query = query.eq("category", category)
    res = query.execute()
    counts = Counter(r.get("category") for r in (res.data or []))
    return [{"category": k, "count": v} for k, v in counts.items()]


def get_status_breakdown(category=None):
    """Returns complaint counts grouped by status."""
    client = get_supabase_client()
    query = client.table("complaints").select("status")
    if category:
        query = query.eq("category", category)
    res = query.execute()
    counts = Counter(r.get("status") for r in (res.data or []))
    return [{"status": k, "count": v} for k, v in counts.items()]


def get_priority_breakdown(category=None):
    """Returns complaint counts grouped by priority."""
    client = get_supabase_client()
    query = client.table("complaints").select("priority")
    if category:
        query = query.eq("category", category)
    res = query.execute()
    counts = Counter(r.get("priority") for r in (res.data or []))
    return [{"priority": k, "count": v} for k, v in counts.items()]


def get_trend_last_days(days=14, category=None):
    """Returns daily complaint counts over the past N days."""
    client = get_supabase_client()
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    query = client.table("complaints").select("created_at").gte("created_at", cutoff)
    if category:
        query = query.eq("category", category)
    res = query.execute()

    day_counts = defaultdict(int)
    for r in res.data or []:
        dt_str = r.get("created_at")
        if dt_str:
            day = dt_str[:10]
            day_counts[day] += 1

    return [{"day": day, "count": count} for day, count in sorted(day_counts.items())]


def get_hotspot_locations(limit=5, category=None):
    """Returns top location hotspots by complaint volume."""
    client = get_supabase_client()
    query = client.table("complaints").select("location_name")
    if category:
        query = query.eq("category", category)
    res = query.execute()

    locations = [r.get("location_name") for r in (res.data or []) if r.get("location_name")]
    counts = Counter(locations).most_common(limit)
    return [{"location_name": loc, "count": count} for loc, count in counts]


def get_complaints_for_map():
    """Retrieves all complaints with geographic coordinates for the civic map."""
    client = get_supabase_client()
    res = (
        client.table("complaints")
        .select("id, category, priority, status, latitude, longitude, location_name")
        .not_.is_("latitude", "null")
        .not_.is_("longitude", "null")
        .execute()
    )
    return res.data or []


# ---------- Feedback ----------

def add_feedback(complaint_id, user_id, rating, comment):
    """Adds citizen feedback and rating for a resolved complaint."""
    client = get_supabase_client()
    payload = {
        "complaint_id": complaint_id,
        "user_id": user_id,
        "rating": int(rating),
        "comment": comment,
    }
    client.table("feedback").insert(payload).execute()


def get_feedback_for_complaint(complaint_id):
    """Retrieves feedback associated with a complaint."""
    client = get_supabase_client()
    res = client.table("feedback").select("*").eq("complaint_id", complaint_id).execute()
    return res.data or []


def get_average_rating(category=None):
    """Calculates average rating and total feedback count."""
    client = get_supabase_client()
    res = client.table("feedback").select("rating, complaints(category)").execute()
    ratings = []
    for r in res.data or []:
        comp = r.get("complaints") or {}
        if category and comp.get("category") != category:
            continue
        if r.get("rating") is not None:
            ratings.append(r["rating"])

    if not ratings:
        return {"avg_rating": 0, "total": 0}
    return {
        "avg_rating": round(sum(ratings) / len(ratings), 1),
        "total": len(ratings),
    }


def get_feedback_by_user(user_id):
    """Retrieves all feedback submitted by a specific user with complaint details."""
    client = get_supabase_client()
    res = (
        client.table("feedback")
        .select("*, complaints(category, description, location_name)")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    items = []
    for r in res.data or []:
        data = dict(r)
        comp = data.pop("complaints", None) or {}
        data["category"] = comp.get("category")
        data["description"] = comp.get("description")
        data["location_name"] = comp.get("location_name")
        items.append(data)
    return items


def get_all_feedback(category=None):
    """Retrieves all feedback with complaint and user details for authority/admin."""
    client = get_supabase_client()
    res = (
        client.table("feedback")
        .select("*, complaints(category, description, location_name), users(name, email)")
        .order("created_at", desc=True)
        .execute()
    )
    items = []
    for r in res.data or []:
        data = dict(r)
        comp = data.pop("complaints", None) or {}
        usr = data.pop("users", None) or {}
        if category and comp.get("category") != category:
            continue
        data["category"] = comp.get("category")
        data["description"] = comp.get("description")
        data["location_name"] = comp.get("location_name")
        data["citizen_name"] = usr.get("name") or "Anonymous Citizen"
        items.append(data)
    return items
