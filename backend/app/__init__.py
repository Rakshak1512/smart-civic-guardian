"""
Application factory for Smart Civic Guardian.
Serves full-stack frontend website, templates, static assets,
and REST API endpoints under a single unified URL for Vercel and local hosting.
All data is stored in Supabase PostgreSQL and private Supabase Storage.
"""

import os
from flask import Flask, jsonify, session, redirect, send_from_directory, request
from flask_cors import CORS
from flask_mail import Mail
from app.config import Config
from app.db import init_db
from app.services.storage_service import get_image_url

mail = Mail()


def create_app():
    # Detect templates and static folders across local and Vercel structures
    curr_dir = os.path.dirname(os.path.abspath(__file__))  # backend/app
    backend_dir = os.path.dirname(curr_dir)  # backend
    project_root = os.path.dirname(backend_dir)  # smart-civic-guardian

    templates_dir = os.path.join(project_root, "frontend", "templates")
    if not os.path.exists(templates_dir):
        templates_dir = os.path.join(backend_dir, "templates")

    public_static_dir = os.path.join(project_root, "public", "static")
    if os.path.exists(public_static_dir):
        static_dir = public_static_dir
    else:
        static_dir = os.path.join(project_root, "frontend", "static")
        if not os.path.exists(static_dir):
            static_dir = os.path.join(backend_dir, "static")

    app = Flask(
        __name__,
        template_folder=templates_dir,
        static_folder=static_dir,
        static_url_path="/static",
    )
    app.config.from_object(Config)

    # Enable CORS
    CORS(
        app,
        supports_credentials=True,
        origins=app.config.get("CORS_ORIGINS", ["*"]),
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    )

    mail.init_app(app)

    # Ensure upload directories exist locally
    os.makedirs(app.config["UPLOAD_FOLDER_ISSUES"], exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER_RESOLVED"], exist_ok=True)

    init_db(app)

    # ---------------------------------------------------------------------------
    # Template Filters & Context Processor
    # ---------------------------------------------------------------------------

    @app.template_filter("ist")
    def to_ist(value):
        """Show a stored UTC timestamp as Indian time."""
        from datetime import datetime, timedelta
        if not value:
            return ""
        try:
            val_clean = str(value).replace("Z", "+00:00")
            dt = datetime.fromisoformat(val_clean)
            if dt.tzinfo is None:
                dt = dt + timedelta(hours=5, minutes=30)
            return dt.strftime("%d %b %Y, %I:%M %p")
        except Exception:
            return str(value)

    @app.template_filter("image_url")
    def image_url_filter(path):
        return get_image_url(path)

    @app.context_processor
    def inject_template_globals():
        return {
            "get_image_url": get_image_url,
            "current_role": session.get("role"),
            "current_name": session.get("name"),
            "unread_count": session.get("unread_count", 0),
        }

    # ---------------------------------------------------------------------------
    # Static Assets Serving Route (Dual-Layer Resilience for Vercel and Local)
    # ---------------------------------------------------------------------------

    @app.route("/static/<path:filename>")
    def serve_static_asset(filename):
        for candidate_dir in [
            os.path.join(project_root, "public", "static"),
            os.path.join(project_root, "frontend", "static"),
            os.path.join(backend_dir, "static"),
        ]:
            full_path = os.path.join(candidate_dir, filename)
            if os.path.exists(full_path) and os.path.isfile(full_path):
                return send_from_directory(candidate_dir, filename)
        return jsonify({"error": f"Static asset '{filename}' not found"}), 404

    @app.route("/css/<path:filename>")
    def serve_css_direct(filename):
        return serve_static_asset(f"css/{filename}")

    @app.route("/js/<path:filename>")
    def serve_js_direct(filename):
        return serve_static_asset(f"js/{filename}")

    @app.route("/images/<path:filename>")
    def serve_images_direct(filename):
        return serve_static_asset(f"images/{filename}")

    # ---------------------------------------------------------------------------
    # Secure Private Image Proxy / Redirect Route
    # ---------------------------------------------------------------------------

    @app.route("/static/uploads/<path:filepath>")
    def serve_uploaded_file(filepath):
        """
        Intercepts static image requests.
        If file exists in local upload directory, serves it.
        Otherwise, fetches signed URL from private Supabase bucket and redirects.
        """
        local_issues = os.path.join(app.config["UPLOAD_FOLDER_ISSUES"], filepath)
        local_resolved = os.path.join(app.config["UPLOAD_FOLDER_RESOLVED"], filepath)

        if os.path.exists(local_issues):
            return send_from_directory(app.config["UPLOAD_FOLDER_ISSUES"], filepath)
        if os.path.exists(local_resolved):
            return send_from_directory(app.config["UPLOAD_FOLDER_RESOLVED"], filepath)

        # Generate Supabase signed URL
        signed = get_image_url(filepath)
        if signed and (signed.startswith("http://") or signed.startswith("https://")):
            return redirect(signed)

        # Check subfolder
        for prefix in ("complaints/", "resolved/"):
            signed_pref = get_image_url(f"{prefix}{filepath}")
            if signed_pref and (signed_pref.startswith("http://") or signed_pref.startswith("https://")):
                return redirect(signed_pref)

        return jsonify({"error": "Image not found"}), 404

    @app.route("/image/<path:photo_path>")
    def get_signed_image(photo_path):
        """Direct signed image redirection endpoint."""
        url = get_image_url(photo_path)
        if url and (url.startswith("http://") or url.startswith("https://")):
            return redirect(url)
        return jsonify({"error": "Image not found"}), 404

    # ---------------------------------------------------------------------------
    # Register All Blueprints
    # ---------------------------------------------------------------------------

    from app.routes.auth_routes import auth_bp
    from app.routes.issue_routes import issue_bp
    from app.routes.admin_routes import admin_bp
    from app.routes.analytics_routes import analytics_bp
    from app.routes.api_routes import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(issue_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(api_bp)

    # ---------------------------------------------------------------------------
    # Global Error Handlers
    # ---------------------------------------------------------------------------

    @app.errorhandler(404)
    def handle_not_found(e):
        if request.path.startswith("/api"):
            return jsonify({
                "error": "Not Found",
                "message": "The requested API endpoint does not exist.",
                "health": "/api/health",
                "documentation": "/api",
            }), 404
        from flask import render_template
        frontend_url = app.config.get("FRONTEND_URL", "http://localhost:3000")
        return render_template(
            "shared/error.html",
            code=404,
            message="The requested page could not be found.",
            error_code=404,
            error_message="Page Not Found",
            FRONTEND_URL=frontend_url,
        ), 404

    @app.errorhandler(413)
    def handle_payload_too_large(e):
        if request.path.startswith("/api"):
            return jsonify({
                "error": "Payload Too Large",
                "message": "Uploaded file is too large (maximum 5MB).",
            }), 413
        from flask import render_template
        frontend_url = app.config.get("FRONTEND_URL", "http://localhost:3000")
        return render_template(
            "shared/error.html",
            code=413,
            message="Uploaded file is too large (maximum 5MB).",
            error_code=413,
            error_message="File too large (max 5MB)",
            FRONTEND_URL=frontend_url,
        ), 413

    @app.errorhandler(500)
    def handle_server_error(e):
        if request.path.startswith("/api"):
            return jsonify({
                "error": "Internal Server Error",
                "message": "An unexpected error occurred on the server.",
            }), 500
        from flask import render_template
        frontend_url = app.config.get("FRONTEND_URL", "http://localhost:3000")
        return render_template(
            "shared/error.html",
            code=500,
            message="An unexpected server error occurred.",
            error_code=500,
            error_message="Internal Server Error",
            FRONTEND_URL=frontend_url,
        ), 500

    return app
