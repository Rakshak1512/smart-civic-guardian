"""
====================================================================
Smart Civic Guardian - Dedicated Frontend Web Service (Port 3000)
Serves the complete frontend website on FRONTEND_URL (http://localhost:3000)
Sends API requests to the separate Backend REST API on BACKEND_URL (http://localhost:5000)
====================================================================
"""

import os
import json
import urllib.request
import urllib.error
from urllib.parse import urlparse
from flask import (
    Flask, Blueprint, request, Response, render_template, redirect, url_for,
    session, flash, jsonify
)
from dotenv import load_dotenv

FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(FRONTEND_DIR)

load_dotenv(os.path.join(FRONTEND_DIR, ".env"))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

ENVIRONMENT = os.environ.get("FLASK_ENV", "development")
IS_PRODUCTION = ENVIRONMENT.lower() in ("production", "prod")

def normalise_service_url(variable_name, default):
    """Trim pasted whitespace and validate a single-line HTTP(S) service URL."""
    value = str(os.environ.get(variable_name, default) or default).strip().rstrip('/')
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise RuntimeError(variable_name + ' contains a newline or control character. Set it to a single-line URL in Render.')
    parsed = urlparse(value)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        raise RuntimeError(variable_name + ' must be a complete http(s) URL.')
    return value

FRONTEND_URL = normalise_service_url("FRONTEND_URL", "http://localhost:3000")
BACKEND_URL = normalise_service_url("BACKEND_URL", "http://localhost:5000")
HOST = os.environ.get("HOST", "127.0.0.1").strip()
PORT = int(os.environ.get("PORT", 3000))
SECRET_KEY = os.environ.get("SECRET_KEY", "smart-civic-guardian-secret-key-2026")

app = Flask(
    __name__,
    template_folder=os.path.join(FRONTEND_DIR, "templates"),
    static_folder=os.path.join(FRONTEND_DIR, "static"),
    static_url_path="/static",
)
app.secret_key = SECRET_KEY

HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate",
    "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade"
}


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


@app.context_processor
def inject_template_globals():
    return {
        "BACKEND_URL": BACKEND_URL,
        "FRONTEND_URL": FRONTEND_URL,
        "API_BASE_URL": BACKEND_URL,
        "current_role": session.get("role"),
        "current_name": session.get("name"),
        "unread_count": session.get("unread_count", 0),
        "get_image_url": lambda p: f"{BACKEND_URL}/image/{p}" if p else "",
    }


# ---------------------------------------------------------------------------
# Backend API Caller & Proxy
# ---------------------------------------------------------------------------

class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


backend_opener = urllib.request.build_opener(NoRedirectHandler)


def build_backend_url(endpoint):
    """Build a backend URL after removing accidental surrounding whitespace."""
    clean_endpoint = str(endpoint or '').strip().lstrip('/')
    if any(ord(char) < 32 or ord(char) == 127 for char in clean_endpoint):
        raise ValueError('Backend endpoint contains a newline or control character.')
    return BACKEND_URL + '/' + clean_endpoint


def call_backend(endpoint, method="GET", data=None, headers=None):
    """Helper function to talk to separate Backend REST API."""
    url = build_backend_url(endpoint)
    req_headers = headers or {}
    data_bytes = None

    if data is not None:
        if isinstance(data, (dict, list)):
            req_headers["Content-Type"] = "application/json"
            data_bytes = json.dumps(data).encode("utf-8")
        elif isinstance(data, bytes):
            data_bytes = data

    req = urllib.request.Request(url, data=data_bytes, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            content = resp.read()
            return json.loads(content.decode("utf-8")), resp.status
    except urllib.error.HTTPError as err:
        try:
            return json.loads(err.read().decode("utf-8")), err.code
        except Exception:
            return {"error": err.reason}, err.code
    except Exception as exc:
        return {"error": str(exc)}, 500


def forward_request_to_backend(path):
    """Forwards incoming browser multipart/form-data or requests directly to Backend."""
    target_url = build_backend_url(path)
    if request.query_string:
        target_url += f"?{request.query_string.decode('utf-8')}"

    req_headers = {}
    for key, value in request.headers.items():
        if key.lower() not in HOP_BY_HOP and key.lower() != "host":
            req_headers[key] = value

    req_headers["Host"] = urlparse(BACKEND_URL).netloc
    req_headers["X-Forwarded-For"] = request.remote_addr or "127.0.0.1"
    req_headers["X-Forwarded-Host"] = request.host

    # Forward session cookie if present
    if "Cookie" in request.headers:
        req_headers["Cookie"] = request.headers["Cookie"]

    body = request.get_data() if request.method in ("POST", "PUT", "PATCH") else None

    req = urllib.request.Request(target_url, data=body, headers=req_headers, method=request.method)
    try:
        resp = backend_opener.open(req, timeout=30)
        content = resp.read()
        resp_headers = []
        for k, v in resp.getheaders():
            if k.lower() not in HOP_BY_HOP:
                if k.lower() == "location":
                    v = v.replace(BACKEND_URL, FRONTEND_URL).replace("http://127.0.0.1:5000", FRONTEND_URL).replace("http://localhost:5000", FRONTEND_URL)
                resp_headers.append((k, v))
        return Response(content, status=resp.status, headers=resp_headers)
    except urllib.error.HTTPError as err:
        # Handles 301, 302, 303 redirects intercepted by NoRedirectHandler
        if err.code in (301, 302, 303, 307, 308):
            loc = err.headers.get("Location", "")
            loc = loc.replace(BACKEND_URL, FRONTEND_URL).replace("http://127.0.0.1:5000", FRONTEND_URL).replace("http://localhost:5000", FRONTEND_URL)
            resp_headers = [("Location", loc)]
            for k, v in err.headers.items():
                if k.lower() == "set-cookie":
                    resp_headers.append((k, v))
            return Response("", status=err.code, headers=resp_headers)

        err_content = err.read()
        resp_headers = [(k, v) for k, v in err.headers.items() if k.lower() not in HOP_BY_HOP]
        return Response(err_content, status=err.code, headers=resp_headers)
    except Exception as exc:
        return jsonify({"error": "Backend Connection Error", "message": str(exc)}), 502


@app.route("/api/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def api_proxy(path):
    return forward_request_to_backend(f"api/{path}")


@app.route("/static/uploads/<path:filename>")
@app.route("/uploads/<path:filename>")
def serve_backend_uploads(filename):
    return redirect(f"{BACKEND_URL}/static/uploads/{filename}")


# ---------------------------------------------------------------------------
# Blueprints: Matching all application endpoints
# ---------------------------------------------------------------------------

auth_bp = Blueprint("auth", __name__)
issue_bp = Blueprint("issue", __name__)
admin_bp = Blueprint("admin", __name__)
analytics_bp = Blueprint("analytics", __name__)


# --- Auth Blueprint ---

@auth_bp.route("/")
@auth_bp.route("/home")
def home():
    return forward_request_to_backend("home")


@auth_bp.route("/about")
def about():
    return forward_request_to_backend("about")


@auth_bp.route("/contact", methods=["GET", "POST"])
def contact():
    return forward_request_to_backend("contact")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    return forward_request_to_backend("login")


@auth_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    return forward_request_to_backend("admin/login")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    return forward_request_to_backend("register")


@auth_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    return forward_request_to_backend("verify-otp")


@auth_bp.route("/resend-otp", methods=["POST"])
def resend_otp():
    return forward_request_to_backend("resend-otp")


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    return forward_request_to_backend("forgot-password")


@auth_bp.route("/verify-reset-otp", methods=["GET", "POST"])
def verify_reset_otp():
    return forward_request_to_backend("verify-reset-otp")


@auth_bp.route("/resend-reset-otp", methods=["POST"])
def resend_reset_otp():
    return forward_request_to_backend("resend-reset-otp")


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    return forward_request_to_backend("reset-password")


@auth_bp.route("/logout")
def logout():
    return forward_request_to_backend("logout")


@auth_bp.route("/dashboard")
def dashboard_redirect():
    return forward_request_to_backend("dashboard")


@auth_bp.route("/profile", methods=["GET", "POST"])
def profile():
    return forward_request_to_backend("profile")


# --- Issue Blueprint ---

@issue_bp.route("/report-issue", methods=["GET", "POST"])
def report_issue():
    return forward_request_to_backend("report-issue")


@issue_bp.route("/report-issue/analyze", methods=["POST"])
def analyze_photo():
    return forward_request_to_backend("report-issue/analyze")


@issue_bp.route("/my-complaints")
def my_complaints():
    return forward_request_to_backend("my-complaints")


@issue_bp.route("/track-status/<int:complaint_id>")
def track_status(complaint_id):
    return forward_request_to_backend(f"track-status/{complaint_id}")


@issue_bp.route("/submit-feedback/<int:complaint_id>", methods=["POST"])
def submit_feedback(complaint_id):
    return forward_request_to_backend(f"submit-feedback/{complaint_id}")


@issue_bp.route("/my-feedback")
def my_feedback():
    return forward_request_to_backend("my-feedback")


@issue_bp.route("/civic-map")
def civic_map():
    return forward_request_to_backend("civic-map")


@issue_bp.route("/notifications")
def notifications():
    return forward_request_to_backend("notifications")


@issue_bp.route("/api/notifications/unread-count")
def unread_count():
    return forward_request_to_backend("api/notifications/unread-count")


# --- Admin Blueprint ---

@admin_bp.route("/admin/dashboard")
def dashboard():
    return forward_request_to_backend("admin/dashboard")


@admin_bp.route("/admin/complaints")
def manage_complaints():
    return forward_request_to_backend("admin/complaints")


@admin_bp.route("/admin/complaints/<int:complaint_id>")
def complaint_detail(complaint_id):
    return forward_request_to_backend(f"admin/complaints/{complaint_id}")


@admin_bp.route("/admin/complaints/<int:complaint_id>/assign", methods=["POST"])
def assign_complaint(complaint_id):
    return forward_request_to_backend(f"admin/complaints/{complaint_id}/assign")


@admin_bp.route("/admin/complaints/<int:complaint_id>/status", methods=["POST"])
def update_status(complaint_id):
    return forward_request_to_backend(f"admin/complaints/{complaint_id}/status")


@admin_bp.route("/admin/map")
def complaints_map():
    return forward_request_to_backend("admin/map")


@admin_bp.route("/admin/panel")
def admin_panel():
    return forward_request_to_backend("admin/panel")


@admin_bp.route("/admin/messages")
def view_messages():
    return forward_request_to_backend("admin/messages")


@admin_bp.route("/admin/messages/<int:message_id>/reply", methods=["POST"])
def reply_message(message_id):
    return forward_request_to_backend(f"admin/messages/{message_id}/reply")


@admin_bp.route("/admin/authorities/add", methods=["POST"])
def add_authority():
    return forward_request_to_backend("admin/authorities/add")


@admin_bp.route("/admin/authorities/<int:user_id>/remove", methods=["POST"])
def remove_authority(user_id):
    return forward_request_to_backend(f"admin/authorities/{user_id}/remove")


@admin_bp.route("/admin/departments")
def departments():
    return forward_request_to_backend("admin/departments")


@admin_bp.route("/admin/users")
def users():
    return forward_request_to_backend("admin/users")


@admin_bp.route("/admin/feedback")
def feedback_list():
    return forward_request_to_backend("admin/feedback")


# --- Analytics Blueprint ---

@analytics_bp.route("/admin/analytics")
def analytics_page():
    return forward_request_to_backend("admin/analytics")


@analytics_bp.route("/api/analytics/summary")
def analytics_summary():
    return forward_request_to_backend("api/analytics/summary")


# Register all blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(issue_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(analytics_bp)


@app.errorhandler(404)
def handle_404(e):
    return render_template("shared/error.html", code=404, message="Page not found on frontend."), 404


@app.errorhandler(500)
def handle_500(e):
    return render_template("shared/error.html", code=500, message="An internal error occurred on the frontend."), 500


if __name__ == "__main__":
    print("============================================================")
    print("  Smart Civic Guardian - Dedicated Frontend Web Service     ")
    print(f"  * Frontend Web URL : {FRONTEND_URL}                       ")
    print(f"  * Backend REST API : {BACKEND_URL}                        ")
    print("============================================================")
    app.run(debug=not IS_PRODUCTION, host=HOST, port=PORT)
