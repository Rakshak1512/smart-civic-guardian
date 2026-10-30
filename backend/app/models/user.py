"""
User model for Smart Civic Guardian.
Handles all database operations for users (citizens, authorities, admins)
directly on Supabase PostgreSQL.
"""

from werkzeug.security import generate_password_hash, check_password_hash
from app.db import get_supabase_client


def create_user(name, email, phone, password, role, age=None, description=None):
    """Creates a new user record in Supabase PostgreSQL."""
    client = get_supabase_client()
    password_hash = generate_password_hash(password)
    payload = {
        "name": name,
        "email": email.strip().lower(),
        "phone": phone,
        "password_hash": password_hash,
        "role": role,
    }
    if age is not None:
        try:
            payload["age"] = int(age)
        except (ValueError, TypeError):
            payload["age"] = None
    if description:
        payload["description"] = description

    res = client.table("users").insert(payload).execute()
    if res.data and len(res.data) > 0:
        return res.data[0]["id"]
    return None


def get_user_by_email(email):
    """Retrieves a user by lowercase email address from Supabase."""
    client = get_supabase_client()
    res = client.table("users").select("*").ilike("email", email.strip().lower()).execute()
    if res.data and len(res.data) > 0:
        return res.data[0]
    return None


def get_user_by_id(user_id):
    """Retrieves a user by primary key ID."""
    client = get_supabase_client()
    res = client.table("users").select("*").eq("id", user_id).execute()
    if res.data and len(res.data) > 0:
        return res.data[0]
    return None


def verify_password(user_row, password):
    """Verifies a plaintext password against the stored password_hash."""
    if not user_row or not user_row.get("password_hash"):
        return False
    return check_password_hash(user_row["password_hash"], password)


def email_exists(email):
    """Returns True if the email already exists in Supabase."""
    return get_user_by_email(email) is not None


def get_all_authorities():
    """Retrieves all authority accounts along with their department and designation."""
    client = get_supabase_client()
    res = client.table("authorities").select("department, designation, users!authorities_user_id_fkey(id, name, email)").execute()
    records = []
    for item in res.data or []:
        user_info = item.get("users") or {}
        records.append({
            "id": user_info.get("id"),
            "name": user_info.get("name"),
            "email": user_info.get("email"),
            "department": item.get("department"),
            "designation": item.get("designation"),
        })
    return records


def get_users_by_role(role):
    """Retrieves all users matching the specified role."""
    client = get_supabase_client()
    res = client.table("users").select("*").eq("role", role).order("name").execute()
    return res.data or []


def update_password(user_id, new_password):
    """Updates a user's password hash in Supabase PostgreSQL."""
    client = get_supabase_client()
    password_hash = generate_password_hash(new_password)
    client.table("users").update({"password_hash": password_hash}).eq("id", user_id).execute()


def get_authorities_by_department_keyword(keyword):
    """Finds authority users matching a department keyword."""
    client = get_supabase_client()
    res = client.table("authorities").select("department, designation, users!authorities_user_id_fkey(id, name, email)").ilike("department", f"%{keyword}%").execute()
    records = []
    for item in res.data or []:
        user_info = item.get("users") or {}
        records.append({
            "id": user_info.get("id"),
            "name": user_info.get("name"),
            "email": user_info.get("email"),
            "department": item.get("department"),
            "designation": item.get("designation"),
        })
    return records


def get_authority_accounts():
    """Returns all authority accounts for administration."""
    return get_all_authorities()


def count_assigned_complaints(user_id):
    """Counts complaints assigned to an authority user."""
    client = get_supabase_client()
    res = client.table("complaints").select("id", count="exact").eq("assigned_to", user_id).execute()
    return res.count or 0


def delete_authority(user_id):
    """Removes an authority account and updates any assigned complaints."""
    client = get_supabase_client()
    user = get_user_by_id(user_id)
    if not user or user.get("role") != "authority":
        return False
    # Unassign complaints
    client.table("complaints").update({"assigned_to": None}).eq("assigned_to", user_id).execute()
    client.table("notifications").delete().eq("user_id", user_id).execute()
    client.table("password_resets").delete().eq("user_id", user_id).execute()
    client.table("authorities").delete().eq("user_id", user_id).execute()
    client.table("users").delete().eq("id", user_id).execute()
    return True
