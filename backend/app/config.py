"""
Application configuration for Smart Civic Guardian.
Reads settings from environment variables (.env) with safe defaults.
"""

import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/
PROJECT_ROOT = os.path.dirname(BASE_DIR)  # smart-civic-guardian/

load_dotenv(os.path.join(BASE_DIR, ".env"))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


class Config:
    ENVIRONMENT = os.environ.get("FLASK_ENV", os.environ.get("ENV", "development"))
    IS_PRODUCTION = ENVIRONMENT.lower() in ("production", "prod")
    DEBUG = not IS_PRODUCTION and os.environ.get("FLASK_DEBUG", "1") in ("1", "true", "True")

    SECRET_KEY = os.environ.get("SECRET_KEY", "smart-civic-guardian-secure-session-key-2026")

    # Host & Port
    HOST = os.environ.get("HOST", "0.0.0.0" if IS_PRODUCTION else "127.0.0.1")
    PORT = int(os.environ.get("PORT", 5000))
    BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:5000").strip().rstrip("/")
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000").strip().rstrip("/")

    # Allowed CORS Origins
    raw_origins = os.environ.get("CORS_ORIGINS", "")
    if raw_origins:
        CORS_ORIGINS = [o.strip().rstrip("/") for o in raw_origins.split(",") if o.strip()]
    else:
        CORS_ORIGINS = ["*"]

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = IS_PRODUCTION

    # Email settings (Gmail SMTP)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() in ("true", "1", "yes")
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER") or MAIL_USERNAME

    # Supabase PostgreSQL & Storage configuration
    DATABASE_URL = os.environ.get("DATABASE_URL")
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://dkjqzqznubizkjewfeyp.supabase.co")
    SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")
    SUPABASE_KEY = SUPABASE_SERVICE_ROLE_KEY
    SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "images")

    # File uploads
    TEMPLATES_FOLDER = os.path.join(PROJECT_ROOT, "frontend", "templates")
    STATIC_FOLDER = os.path.join(PROJECT_ROOT, "frontend", "static")
    UPLOAD_FOLDER_ISSUES = os.path.join(STATIC_FOLDER, "uploads", "issue_photos")
    UPLOAD_FOLDER_RESOLVED = os.path.join(STATIC_FOLDER, "uploads", "resolved_photos")
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB max image upload

    # Heuristics & Duplicate detection
    DUPLICATE_DISTANCE_METERS = 150
