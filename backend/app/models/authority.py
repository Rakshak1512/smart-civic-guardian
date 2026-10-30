"""
Authority model for Smart Civic Guardian.
Stores extra profile info (department / designation) in Supabase PostgreSQL.
"""

from app.db import get_supabase_client


def create_authority_profile(user_id, department, designation):
    """Creates or updates an authority profile in Supabase."""
    client = get_supabase_client()
    payload = {
        "user_id": user_id,
        "department": department,
        "designation": designation,
    }
    client.table("authorities").insert(payload).execute()


def get_authority_profile(user_id):
    """Retrieves an authority profile by user_id."""
    client = get_supabase_client()
    res = client.table("authorities").select("*").eq("user_id", user_id).execute()
    if res.data and len(res.data) > 0:
        return res.data[0]
    return None


def delete_authority(user_id):
    """Removes an authority profile and user."""
    client = get_supabase_client()
    client.table("authorities").delete().eq("user_id", user_id).execute()
    client.table("users").delete().eq("id", user_id).execute()


# Aliases for backward compatibility
get_authority_by_user_id = get_authority_profile
create_authority = create_authority_profile
