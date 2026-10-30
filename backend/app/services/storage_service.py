"""
Supabase Storage service for Smart Civic Guardian.
Handles secure uploads to the private 'images' Supabase Storage bucket,
enforces 5MB size limits, validates JPEG/PNG/WebP formats,
and generates signed URLs for secure private image viewing.
"""

import os
import uuid
from flask import current_app
from app.db import get_supabase_client

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
DEFAULT_SIGNED_URL_EXPIRY = 3600  # 1 hour


def validate_image_file(file_storage):
    """
    Validates file presence, extension, and file size (max 5 MB).
    Raises ValueError on validation failure.
    """
    if not file_storage or not getattr(file_storage, "filename", None) or file_storage.filename == "":
        return False

    filename = file_storage.filename
    if "." not in filename:
        raise ValueError("Invalid file format. Must have an extension.")

    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Invalid image type '.{ext}'. Allowed formats: JPEG, PNG, and WebP.")

    # Check size
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)

    if size > MAX_IMAGE_SIZE_BYTES:
        raise ValueError("Image file exceeds the maximum allowed size of 5 MB.")

    return True


def save_photo(file_storage, folder_type="issue_photos"):
    """
    Uploads an image to the private Supabase Storage bucket 'images'.
    Stores in path: complaints/{uuid}.{ext} or resolved/{uuid}.{ext}
    Returns the storage object key (e.g. 'complaints/abc.png').
    """
    if not file_storage or not getattr(file_storage, "filename", None) or file_storage.filename == "":
        return None

    validate_image_file(file_storage)

    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    if ext == "jpg":
        ext = "jpeg"
    mime_type = f"image/{ext}"

    subfolder = "resolved" if folder_type == "resolved_photos" else "complaints"
    object_name = f"{subfolder}/{uuid.uuid4().hex}.{ext}"
    bucket_name = current_app.config.get("SUPABASE_BUCKET", "images") if current_app else "images"

    try:
        client = get_supabase_client()
        file_bytes = file_storage.read()
        client.storage.from_(bucket_name).upload(
            object_name,
            file_bytes,
            file_options={"content-type": mime_type, "upsert": "true"},
        )
        return object_name
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Supabase storage upload error: {e}")
        # Local upload folder fallback if network fails
        target_dir = current_app.config["UPLOAD_FOLDER_RESOLVED"] if folder_type == "resolved_photos" else current_app.config["UPLOAD_FOLDER_ISSUES"]
        os.makedirs(target_dir, exist_ok=True)
        local_filename = f"{uuid.uuid4().hex}.{ext}"
        full_path = os.path.join(target_dir, local_filename)
        file_storage.seek(0)
        file_storage.save(full_path)
        return local_filename


def get_image_url(photo_path, expires_in=DEFAULT_SIGNED_URL_EXPIRY):
    """
    Generates a secure signed URL for an image stored in the private Supabase bucket.
    If the path is already a full URL or a local file, returns the appropriate accessible URL.
    """
    if not photo_path:
        return None

    # Already a full URL
    if str(photo_path).startswith("http://") or str(photo_path).startswith("https://"):
        return photo_path

    # Check if this is a Supabase object path (e.g. complaints/... or resolved/...)
    if "/" in str(photo_path) and not str(photo_path).startswith("/"):
        try:
            client = get_supabase_client()
            bucket_name = current_app.config.get("SUPABASE_BUCKET", "images") if current_app else "images"
            signed = client.storage.from_(bucket_name).create_signed_url(photo_path, expires_in)
            if signed and "signedURL" in signed:
                return signed["signedURL"]
            if signed and "signedUrl" in signed:
                return signed["signedUrl"]
        except Exception as e:
            if current_app:
                current_app.logger.warning(f"Error generating signed URL for {photo_path}: {e}")

    # Fallback to local static uploads
    return f"/static/uploads/issue_photos/{photo_path}"
