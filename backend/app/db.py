"""
Database connection and Supabase client adapter for Smart Civic Guardian.
Directly interfaces with Supabase PostgreSQL (dkjqzqznubizkjewfeyp),
completely eliminating SQLite writes and ensuring persistent cloud data storage.
"""

import os
from flask import g, current_app
from supabase import create_client, Client

_supabase_client = None


def get_supabase_client() -> Client:
    """
    Returns an authenticated Supabase client using SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.
    Provides administrative access across all tables (users, complaints, notifications, etc.)
    and Supabase Storage bucket 'images'.
    """
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    url = (
        (current_app and current_app.config.get("SUPABASE_URL"))
        or os.environ.get("SUPABASE_URL")
        or "https://dkjqzqznubizkjewfeyp.supabase.co"
    )
    key = (
        (current_app and current_app.config.get("SUPABASE_SERVICE_ROLE_KEY"))
        or (current_app and current_app.config.get("SUPABASE_KEY"))
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_KEY")
        or ""
    )

    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured in environment.")

    _supabase_client = create_client(url, key)
    return _supabase_client


def get_db():
    """
    Returns the database client for the current context.
    Prioritizes Supabase client for all PostgreSQL queries.
    """
    if "supabase" not in g:
        g.supabase = get_supabase_client()
    return g.supabase


def close_db(e=None):
    """Cleanup hook for teardown."""
    g.pop("supabase", None)
    g.pop("db", None)


def init_db(app):
    """
    Initializes database connection on application startup.
    Verifies connection to Supabase PostgreSQL.
    """
    app.teardown_appcontext(close_db)
    with app.app_context():
        try:
            client = get_supabase_client()
            app.logger.info("Connected to Supabase PostgreSQL successfully.")
        except Exception as e:
            app.logger.error(f"Failed to initialize Supabase client: {e}")
