"""
Comprehensive REST API Blueprint for Smart Civic Guardian.
Provides full JSON-based API endpoints for citizens, authorities, and administrators.
"""

import os
from flask import (
    Blueprint, request, jsonify, session, current_app, send_from_directory
)
from app.models import (
    user as user_model,
    issue as issue_model,
    authority as authority_model,
    notification as notification_model,
    contact_message as contact_model,
    password_reset as reset_model,
)
from app.services import (
    ai_detection_service,
    duplicate_detection_service,
    location_service,
    notification_service,
    storage_service,
)

api_bp = Blueprint("api", __name__)


# ---------------------------------------------------------------------------
# Helper: Authentication Decorators / Checks
# ---------------------------------------------------------------------------

def get_current_user():
    """Retrieves current user from session or returns None."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return user_model.get_user_by_id(user_id)


def require_auth(roles=None):
    """Verifies that the requester is authenticated and has the required role."""
    user = get_current_user()
    if not user:
        return None, (jsonify({"error": "Unauthorized", "message": "Authentication required"}), 401)
    if roles and user["role"] not in roles:
        return None, (jsonify({"error": "Forbidden", "message": f"Requires one of roles: {roles}"}), 403)
    return user, None


# ---------------------------------------------------------------------------
# Health & API Info Endpoints
# ---------------------------------------------------------------------------

@api_bp.route("/", methods=["GET"])
def api_root():
    """Backend Root: Responds with JSON API information, NOT the frontend homepage."""
    frontend_url = current_app.config.get("FRONTEND_URL", "http://localhost:3000")
    return jsonify({
        "status": "success",
        "service": "Smart Civic Guardian REST API Server",
        "message": "Smart Civic Guardian Backend REST API is running",
        "version": "1.0.0",
        "health": "/api/health",
        "documentation": "/api",
        "frontend_url": frontend_url,
    })


@api_bp.route("/api/health", methods=["GET"])
def api_health():
    """Health check endpoint specified in Master Prompt."""
    return jsonify({
        "status": "success",
        "message": "Smart Civic Guardian API is running"
    })


@api_bp.route("/api", methods=["GET"])
def api_info():
    """Provides complete API information and endpoint groups."""
    return jsonify({
        "name": "Smart Civic Guardian REST API",
        "version": "1.0.0",
        "description": "Full-stack civic issue reporting and management REST API",
        "endpoint_groups": {
            "health": ["GET /api/health"],
            "auth": [
                "POST /api/auth/register",
                "POST /api/auth/login",
                "POST /api/auth/logout",
                "GET /api/auth/me",
                "POST /api/auth/forgot-password",
                "POST /api/auth/reset-password",
            ],
            "complaints": [
                "GET /api/complaints",
                "GET /api/complaints/my",
                "POST /api/complaints",
                "POST /api/complaints/analyze",
                "GET /api/complaints/<id>",
                "GET /api/complaints/<id>/track",
                "POST /api/complaints/<id>/feedback",
            ],
            "admin": [
                "GET /api/admin/dashboard",
                "GET /api/admin/complaints",
                "GET /api/admin/complaints/<id>",
                "POST /api/admin/complaints/<id>/assign",
                "POST /api/admin/complaints/<id>/status",
                "GET /api/admin/authorities",
                "POST /api/admin/authorities",
                "DELETE /api/admin/authorities/<user_id>",
                "GET /api/admin/users",
                "GET /api/admin/messages",
                "POST /api/admin/messages/<id>/reply",
                "GET /api/admin/map",
            ],
            "analytics": [
                "GET /api/analytics/summary"
            ],
            "notifications": [
                "GET /api/notifications",
                "POST /api/notifications/read",
            ],
            "contact": [
                "POST /api/contact"
            ],
        },
    })


# ---------------------------------------------------------------------------
# Auth API Endpoints (with Email OTP Verification)
# ---------------------------------------------------------------------------

@api_bp.route("/api/auth/send-registration-otp", methods=["POST"])
def auth_send_registration_otp():
    """Validates form fields and dispatches a 6-digit OTP for new registrations."""
    from app.services import otp_service
    from datetime import datetime, timedelta

    data = request.get_json(silent=True) or request.form
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    phone = data.get("phone", "").strip()
    password = data.get("password", "")
    role = data.get("role", "citizen").strip().lower()

    if not name or not email or not password:
        return jsonify({"error": "Bad Request", "message": "Name, email, and password are required."}), 400

    if role not in ("citizen", "authority"):
        return jsonify({"error": "Bad Request", "message": "Role must be 'citizen' or 'authority'."}), 400

    if user_model.email_exists(email):
        return jsonify({"error": "Conflict", "message": "An account with this email already exists."}), 409

    otp_code = otp_service.generate_otp()
    ok, challenge_id, store_err = otp_service.store_otp_challenge(email, otp_code, purpose="registration")
    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=otp_service.OTP_EXPIRY_MINUTES)

    sent, mail_err = otp_service.send_otp_email(email, otp_code, purpose="Registration Verification")
    if not sent:
        return jsonify({"error": "Mail Error", "message": f"Could not send email: {mail_err}"}), 500

    session["pending_reg"] = {
        "name": name,
        "email": email,
        "phone": phone,
        "password": password,
        "role": role,
        "department": data.get("department", "General"),
        "designation": data.get("designation", "Officer"),
        "age": data.get("age"),
        "description": data.get("description", ""),
        "challenge_id": challenge_id,
        "expires_at": expires_at.isoformat(),
        "attempts": 0,
        "last_sent": now.isoformat(),
    }

    return jsonify({
        "success": True,
        "message": f"6-digit verification code sent to {email}.",
        "email": email,
        "expires_in": 300,
    })


@api_bp.route("/api/auth/verify-registration-otp", methods=["POST"])
def auth_verify_registration_otp():
    """Verifies registration OTP and creates account in Supabase PostgreSQL."""
    from app.services import otp_service
    from datetime import datetime

    data = request.get_json(silent=True) or request.form
    entered_otp = data.get("otp", "").strip()
    pending = session.get("pending_reg")

    if not pending:
        return jsonify({"error": "Session Expired", "message": "No active registration session."}), 400

    if not entered_otp or len(entered_otp) != 6 or not entered_otp.isdigit():
        return jsonify({"error": "Bad Request", "message": "Please provide a valid 6-digit OTP code."}), 400

    # Expiry
    try:
        exp_dt = datetime.fromisoformat(pending["expires_at"])
        if datetime.utcnow() > exp_dt:
            return jsonify({"error": "Expired", "message": "Verification code expired. Please request a new code."}), 400
    except Exception:
        pass

    # Verify Peppered HMAC from PostgreSQL email_otps table
    verified, verify_msg = otp_service.verify_stored_otp(pending["email"], entered_otp, purpose="registration")
    if not verified:
        return jsonify({"error": "Verification Failed", "message": verify_msg}), 400

    # Insert into Supabase
    user_id = user_model.create_user(
        name=pending["name"],
        email=pending["email"],
        phone=pending["phone"],
        password=pending["password"],
        role=pending["role"],
        age=pending.get("age"),
        description=pending.get("description"),
    )

    if pending["role"] == "authority" and user_id:
        authority_model.create_authority_profile(
            user_id=user_id,
            department=pending.get("department", "General"),
            designation=pending.get("designation", "Officer"),
        )

    session.pop("pending_reg", None)
    return jsonify({
        "success": True,
        "message": "Account created successfully in Supabase PostgreSQL.",
        "user_id": user_id,
    }), 201


@api_bp.route("/api/auth/register", methods=["POST"])
def auth_register():
    data = request.get_json(silent=True) or request.form
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    phone = data.get("phone", "").strip()
    password = data.get("password", "")
    role = data.get("role", "citizen").strip().lower()
    age = data.get("age") or None
    description = data.get("description", "").strip() or None

    if not name or not email or not password:
        return jsonify({"error": "Bad Request", "message": "Name, email, and password are required."}), 400

    if role not in ("citizen", "authority"):
        return jsonify({"error": "Bad Request", "message": "Role must be 'citizen' or 'authority'."}), 400

    if user_model.email_exists(email):
        return jsonify({"error": "Conflict", "message": "Email is already registered."}), 409

    try:
        user_id = user_model.create_user(name, email, phone, password, role, age=age, description=description)

        if role == "authority":
            department = data.get("department", "General").strip()
            designation = data.get("designation", "Officer").strip()
            authority_model.create_authority_profile(user_id, department, designation)

        user = user_model.get_user_by_id(user_id)
        session["user_id"] = user["id"]
        session["role"] = user["role"]
        session["name"] = user["name"]

        return jsonify({
            "success": True,
            "message": "User registered successfully",
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"],
            },
        }), 201
    except Exception as e:
        return jsonify({"error": "Internal Error", "message": str(e)}), 500


@api_bp.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(silent=True) or request.form
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Bad Request", "message": "Email and password are required."}), 400

    user = user_model.get_user_by_email(email)
    if not user or not user_model.verify_password(user, password):
        return jsonify({"error": "Unauthorized", "message": "Invalid email or password."}), 401

    session["user_id"] = user["id"]
    session["role"] = user["role"]
    session["name"] = user["name"]

    user_data = {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
    }

    if user["role"] == "authority":
        auth_row = authority_model.get_authority_profile(user["id"])
        if auth_row:
            auth_info = dict(auth_row)
            session["department"] = auth_info.get("department")
            session["designation"] = auth_info.get("designation")
            user_data["department"] = auth_info.get("department")
            user_data["designation"] = auth_info.get("designation")

    return jsonify({
        "success": True,
        "message": "Login successful",
        "user": user_data,
    })


@api_bp.route("/api/auth/logout", methods=["POST", "GET"])
def auth_logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully."})


@api_bp.route("/api/auth/me", methods=["GET"])
def auth_me():
    user = get_current_user()
    if not user:
        return jsonify({"authenticated": False}), 401

    user_info = {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "phone": user.get("phone"),
    }
    if user["role"] == "authority":
        auth_row = authority_model.get_authority_profile(user["id"])
        if auth_row:
            auth_info = dict(auth_row)
            user_info["department"] = auth_info.get("department")
            user_info["designation"] = auth_info.get("designation")

    return jsonify({"authenticated": True, "user": user_info})


@api_bp.route("/api/auth/forgot-password", methods=["POST"])
def auth_forgot_password():
    """Generates a 6-digit OTP, stores hashed token in Supabase, and emails via SMTP."""
    from app.services import otp_service
    from datetime import datetime, timedelta

    data = request.get_json(silent=True) or request.form
    email = data.get("email", "").strip().lower()
    user = user_model.get_user_by_email(email)

    if user:
        otp_code = otp_service.generate_otp()
        ok, challenge_id, store_err = otp_service.store_otp_challenge(email, otp_code, purpose="password_reset")
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=otp_service.OTP_EXPIRY_MINUTES)

        sent, mail_err = otp_service.send_otp_email(email, otp_code, purpose="Password Reset")
        if not sent:
            return jsonify({"error": "Mail Error", "message": f"Could not send email: {mail_err}"}), 500

        session["api_reset"] = {
            "user_id": user["id"],
            "email": email,
            "challenge_id": challenge_id,
            "expires_at": expires_at.isoformat(),
            "attempts": 0,
        }

        return jsonify({
            "success": True,
            "message": f"6-digit reset OTP sent to {email}.",
            "email": email,
        })

    return jsonify({"success": True, "message": "If that email exists, a reset OTP has been processed."})


@api_bp.route("/api/auth/verify-reset-otp", methods=["POST"])
def auth_verify_reset_otp():
    """Verifies the 6-digit reset OTP against Supabase email_otps table."""
    from app.services import otp_service
    from datetime import datetime

    data = request.get_json(silent=True) or request.form
    entered_otp = data.get("otp", "").strip()
    reset_state = session.get("api_reset")

    if not reset_state:
        return jsonify({"error": "Session Expired", "message": "No active password reset session."}), 400

    if not entered_otp or len(entered_otp) != 6 or not entered_otp.isdigit():
        return jsonify({"error": "Bad Request", "message": "Please enter all 6 digits of the OTP."}), 400

    verified, verify_msg = otp_service.verify_stored_otp(reset_state["email"], entered_otp, purpose="password_reset")
    if not verified:
        return jsonify({"error": "Invalid Code", "message": verify_msg}), 400

    session["verified_reset_user_id"] = reset_state["user_id"]
    session.pop("api_reset", None)

    return jsonify({"success": True, "message": "Code verified. You may now reset your password."})


@api_bp.route("/api/auth/reset-password", methods=["POST"])
def auth_reset_password():
    data = request.get_json(silent=True) or request.form
    new_password = data.get("password", "")
    token = data.get("token", "").strip()

    user_id = session.get("verified_reset_user_id")
    if not user_id and token:
        reset_row = reset_model.get_valid_reset(token)
        if reset_row:
            user_id = reset_row["user_id"]
            reset_model.mark_reset_used(token)

    if not user_id or not new_password:
        return jsonify({"error": "Bad Request", "message": "Valid session or token and new password required."}), 400

    user_model.update_password(user_id, new_password)
    session.pop("verified_reset_user_id", None)
    return jsonify({"success": True, "message": "Password updated successfully in Supabase. Please log in."})


# ---------------------------------------------------------------------------
# Complaints API Endpoints
# ---------------------------------------------------------------------------

@api_bp.route("/api/complaints/analyze", methods=["POST"])
def complaints_analyze():
    """Runs AI analysis heuristic on an uploaded photo."""
    photo = request.files.get("photo")
    category = request.form.get("category", "")

    if not photo or not photo.filename:
        return jsonify({"error": "Bad Request", "message": "Photo is required for analysis."}), 400

    try:
        filename = storage_service.save_photo(photo, folder_type="issue_photos")
        photo_full_path = os.path.join(current_app.config["UPLOAD_FOLDER_ISSUES"], filename)
        ai_result = ai_detection_service.detect_category(photo_full_path, category)
        suggested_cat = ai_result.get("category")
        confidence = ai_result.get("confidence")
        priority = ai_result.get("priority", "Medium")

        return jsonify({
            "success": True,
            "filename": filename,
            "photo_url": f"/uploads/issue_photos/{filename}",
            "suggested_category": suggested_cat,
            "confidence": confidence,
            "priority": priority,
        })
    except Exception as e:
        return jsonify({"error": "Analysis Failed", "message": str(e)}), 500


@api_bp.route("/api/complaints", methods=["GET", "POST"])
def complaints_collection():
    if request.method == "GET":
        status = request.args.get("status")
        category = request.args.get("category")
        priority = request.args.get("priority")
        user_id = request.args.get("user_id")

        if user_id:
            complaints = issue_model.get_complaints_by_user(user_id)
        else:
            complaints = issue_model.get_all_complaints(status=status, category=category, priority=priority)

        result = [dict(c) for c in complaints]
        return jsonify({"complaints": result, "count": len(result)})

    # POST: Submit a new complaint
    user, err = require_auth(roles=["citizen", "admin"])
    if err:
        return err

    data = request.form if request.form else (request.get_json(silent=True) or {})
    category = data.get("category", "").strip()
    description = data.get("description", "").strip()
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    location_name = data.get("location_name", "").strip() or data.get("manual_location", "").strip()

    if not category or not description:
        return jsonify({"error": "Bad Request", "message": "Category and description are required."}), 400

    # Handle photo upload
    photo = request.files.get("photo")
    photo_filename = None
    photo_full_path = None

    if photo and photo.filename:
        try:
            photo_filename = storage_service.save_photo(photo, folder_type="issue_photos")
            photo_full_path = os.path.join(current_app.config["UPLOAD_FOLDER_ISSUES"], photo_filename)
        except Exception as e:
            current_app.logger.warning(f"Photo save failed: {e}")

    # Resolve location
    manual_loc = data.get("manual_location", "").strip() or None
    loc = location_service.resolve_location(latitude, longitude, location_name, manual_loc)

    # AI Detection
    ai_result = ai_detection_service.detect_category(photo_full_path, user_selected_category=category)
    final_category = ai_result.get("category") or category
    priority = ai_result.get("priority", "Medium")

    # Duplicate detection
    duplicate = duplicate_detection_service.find_duplicate(
        final_category, loc["latitude"], loc["longitude"], loc["location_name"]
    )

    duplicate_of = None
    duplicate_group = None
    if duplicate:
        dup_dict = dict(duplicate)
        duplicate_of = dup_dict["id"]
        duplicate_group = dup_dict.get("duplicate_group") or f"group-{dup_dict['id']}"
        priority = duplicate_detection_service.escalate_priority_if_needed(dup_dict)
        issue_model.update_status(dup_dict["id"], dup_dict["status"])
        issue_model.increment_support_count(dup_dict["id"])

    complaint_id = issue_model.create_complaint({
        "user_id": user["id"],
        "category": final_category,
        "ai_detected_category": ai_result.get("category"),
        "ai_confidence": ai_result.get("confidence"),
        "description": description,
        "photo_path": photo_filename,
        "latitude": loc["latitude"],
        "longitude": loc["longitude"],
        "location_name": loc["location_name"],
        "priority": priority,
        "duplicate_of": duplicate_of,
        "duplicate_group": duplicate_group,
    })

    # Auto-assign to responsible department authority if available
    try:
        from app.services.notification_service import CATEGORY_DEPARTMENT_KEYWORDS
        keyword = CATEGORY_DEPARTMENT_KEYWORDS.get(final_category)
        if keyword:
            matching = user_model.get_authorities_by_department_keyword(keyword)
            if matching:
                issue_model.update_status(complaint_id, "Pending", assigned_to=matching[0]["id"])
    except Exception as e:
        current_app.logger.warning(f"Auto-assign warning: {e}")

    # Send notifications
    try:
        notification_service.notify_new_complaint(complaint_id, final_category, priority, loc["location_name"])
        if duplicate:
            notification_service.notify_duplicate_linked(user["id"], complaint_id, final_category)
        else:
            notification_service.notify_complaint_submitted(user["id"], complaint_id, final_category, priority)
    except Exception as e:
        current_app.logger.warning(f"Notification error: {e}")

    complaint = issue_model.get_complaint_by_id(complaint_id)
    return jsonify({
        "success": True,
        "message": "Complaint submitted successfully",
        "complaint": dict(complaint) if complaint else {"id": complaint_id},
    }), 201


@api_bp.route("/api/complaints/my", methods=["GET"])
def complaints_my():
    user, err = require_auth(roles=["citizen", "admin"])
    if err:
        return err
    complaints = issue_model.get_complaints_by_user(user["id"])
    return jsonify({"complaints": [dict(c) for c in complaints]})


@api_bp.route("/api/complaints/<int:complaint_id>", methods=["GET"])
def complaint_detail(complaint_id):
    complaint = issue_model.get_complaint_by_id(complaint_id)
    if not complaint:
        return jsonify({"error": "Not Found", "message": "Complaint not found."}), 404

    data = dict(complaint)
    feedback = issue_model.get_feedback_by_complaint(complaint_id)
    data["feedback"] = dict(feedback) if feedback else None
    return jsonify({"complaint": data})


@api_bp.route("/api/complaints/<int:complaint_id>/track", methods=["GET"])
def complaint_track(complaint_id):
    complaint = issue_model.get_complaint_by_id(complaint_id)
    if not complaint:
        return jsonify({"error": "Not Found", "message": "Complaint not found."}), 404

    feedback = issue_model.get_feedback_by_complaint(complaint_id)
    return jsonify({
        "complaint": dict(complaint),
        "feedback": dict(feedback) if feedback else None,
        "status": complaint["status"],
    })


@api_bp.route("/api/complaints/<int:complaint_id>/feedback", methods=["POST"])
def complaint_feedback(complaint_id):
    user, err = require_auth(roles=["citizen", "admin"])
    if err:
        return err

    complaint = issue_model.get_complaint_by_id(complaint_id)
    if not complaint:
        return jsonify({"error": "Not Found", "message": "Complaint not found."}), 404

    if complaint["user_id"] != user["id"] and user["role"] != "admin":
        return jsonify({"error": "Forbidden", "message": "You can only leave feedback on your own complaints."}), 403

    data = request.get_json(silent=True) or request.form
    try:
        rating = int(data.get("rating", 5))
    except ValueError:
        return jsonify({"error": "Bad Request", "message": "Rating must be an integer between 1 and 5."}), 400

    comment = data.get("comment", "").strip()

    feedback_id = issue_model.add_feedback(complaint_id, user["id"], rating, comment)
    return jsonify({
        "success": True,
        "message": "Feedback submitted successfully.",
        "feedback_id": feedback_id,
    })


# ---------------------------------------------------------------------------
# Admin & Authority API Endpoints
# ---------------------------------------------------------------------------

@api_bp.route("/api/admin/dashboard", methods=["GET"])
def admin_dashboard_stats():
    user, err = require_auth(roles=["authority", "admin"])
    if err:
        return err

    category = session.get("department") if user["role"] == "authority" else None
    stats = issue_model.get_stats(category=category)
    return jsonify({"stats": stats, "department": category})


@api_bp.route("/api/admin/complaints", methods=["GET"])
def admin_complaints_list():
    user, err = require_auth(roles=["authority", "admin"])
    if err:
        return err

    status = request.args.get("status")
    category = request.args.get("category")
    priority = request.args.get("priority")
    search = request.args.get("search")

    if user["role"] == "authority" and session.get("department"):
        category = session.get("department")

    complaints = issue_model.get_all_complaints(status=status, category=category, priority=priority, search=search)
    return jsonify({"complaints": [dict(c) for c in complaints]})


@api_bp.route("/api/admin/complaints/<int:complaint_id>", methods=["GET"])
def admin_complaint_get(complaint_id):
    user, err = require_auth(roles=["authority", "admin"])
    if err:
        return err

    complaint = issue_model.get_complaint_by_id(complaint_id)
    if not complaint:
        return jsonify({"error": "Not Found", "message": "Complaint not found."}), 404

    feedback = issue_model.get_feedback_by_complaint(complaint_id)
    authorities = user_model.get_all_authorities()
    return jsonify({
        "complaint": dict(complaint),
        "feedback": dict(feedback) if feedback else None,
        "authorities": [dict(a) for a in authorities],
    })


@api_bp.route("/api/admin/complaints/<int:complaint_id>/assign", methods=["POST"])
def admin_complaint_assign(complaint_id):
    user, err = require_auth(roles=["authority", "admin"])
    if err:
        return err

    complaint = issue_model.get_complaint_by_id(complaint_id)
    if not complaint:
        return jsonify({"error": "Not Found", "message": "Complaint not found."}), 404

    data = request.get_json(silent=True) or request.form
    assigned_to = data.get("assigned_to")

    if assigned_to:
        issue_model.update_status(complaint_id, complaint["status"], assigned_to=int(assigned_to))

    return jsonify({"success": True, "message": "Complaint assigned successfully."})


@api_bp.route("/api/admin/complaints/<int:complaint_id>/status", methods=["POST"])
def admin_complaint_update_status(complaint_id):
    user, err = require_auth(roles=["authority", "admin"])
    if err:
        return err

    complaint = issue_model.get_complaint_by_id(complaint_id)
    if not complaint:
        return jsonify({"error": "Not Found", "message": "Complaint not found."}), 404

    data = request.form if request.form else (request.get_json(silent=True) or {})
    new_status = data.get("status", "").strip()
    notes = data.get("resolution_notes", "").strip()

    if new_status not in ("Pending", "In Progress", "Resolved"):
        return jsonify({"error": "Bad Request", "message": "Invalid status."}), 400

    resolved_photo = request.files.get("resolved_photo")
    resolved_photo_path = None
    if resolved_photo and resolved_photo.filename:
        try:
            resolved_photo_path = storage_service.save_photo(resolved_photo, folder_type="resolved_photos")
        except Exception as e:
            return jsonify({"error": "Upload Error", "message": str(e)}), 400

    issue_model.update_status(
        complaint_id=complaint_id,
        status=new_status,
        resolution_notes=notes,
        resolved_photo_path=resolved_photo_path,
    )

    try:
        notification_service.notify_status_change(
            complaint_id, complaint["user_id"], complaint["category"], new_status
        )
    except Exception as e:
        current_app.logger.warning(f"Notification error: {e}")

    return jsonify({"success": True, "message": f"Complaint status updated to {new_status}."})


@api_bp.route("/api/admin/authorities", methods=["GET", "POST"])
def admin_authorities():
    user, err = require_auth(roles=["admin"])
    if err:
        return err

    if request.method == "GET":
        authorities = user_model.get_all_authorities()
        return jsonify({"authorities": [dict(a) for a in authorities]})

    # POST: Add new authority
    data = request.get_json(silent=True) or request.form
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    department = data.get("department", "").strip()
    designation = data.get("designation", "").strip()
    password = data.get("password", "").strip()

    if not name or not email or not department or not password:
        return jsonify({"error": "Bad Request", "message": "Name, email, department, and password are required."}), 400

    if user_model.email_exists(email):
        return jsonify({"error": "Conflict", "message": "Email is already in use."}), 409

    user_id = user_model.create_user(name, email, phone="", password=password, role="authority")
    authority_model.create_authority(user_id, department, designation)
    return jsonify({"success": True, "message": "Authority created successfully."}), 201


@api_bp.route("/api/admin/authorities/<int:user_id>", methods=["DELETE"])
def admin_authority_remove(user_id):
    user, err = require_auth(roles=["admin"])
    if err:
        return err

    authority_model.delete_authority(user_id)
    return jsonify({"success": True, "message": "Authority removed successfully."})


@api_bp.route("/api/admin/users", methods=["GET"])
def admin_users_list():
    user, err = require_auth(roles=["admin"])
    if err:
        return err

    users = user_model.get_users_by_role("citizen")
    return jsonify({"users": [dict(u) for u in users]})


@api_bp.route("/api/admin/messages", methods=["GET"])
def admin_messages_list():
    user, err = require_auth(roles=["authority", "admin"])
    if err:
        return err

    department = session.get("department") if user["role"] == "authority" else None
    messages = contact_model.get_messages(department=department)
    return jsonify({"messages": [dict(m) for m in messages]})


@api_bp.route("/api/admin/messages/<int:message_id>/reply", methods=["POST"])
def admin_message_reply(message_id):
    user, err = require_auth(roles=["authority", "admin"])
    if err:
        return err

    data = request.get_json(silent=True) or request.form
    reply_text = data.get("reply_text", "").strip()
    if not reply_text:
        return jsonify({"error": "Bad Request", "message": "Reply text is required."}), 400

    contact_model.add_reply(message_id, reply_text)
    return jsonify({"success": True, "message": "Reply saved successfully."})


@api_bp.route("/api/admin/map", methods=["GET"])
def admin_map_data():
    complaints = issue_model.get_complaints_with_location()
    return jsonify({"complaints": [dict(c) for c in complaints]})


# ---------------------------------------------------------------------------
# Analytics API Endpoint
# ---------------------------------------------------------------------------

@api_bp.route("/api/analytics/summary", methods=["GET"])
def analytics_summary():
    user, err = require_auth(roles=["authority", "admin"])
    if err:
        return err

    dept = session.get("department") if user["role"] == "authority" else None
    stats = issue_model.get_stats(category=dept)
    category_rows = issue_model.get_category_breakdown(category=dept)
    status_rows = issue_model.get_status_breakdown(category=dept)
    priority_rows = issue_model.get_priority_breakdown(category=dept)
    trend_rows = issue_model.get_trend_last_days(14, category=dept)
    hotspot_rows = issue_model.get_hotspot_locations(5, category=dept)
    rating = issue_model.get_average_rating(category=dept)

    return jsonify({
        "stats": stats,
        "by_category": {row["category"]: row["count"] for row in category_rows},
        "by_status": {row["status"]: row["count"] for row in status_rows},
        "by_priority": {row["priority"]: row["count"] for row in priority_rows},
        "trend": [{"day": row["day"], "count": row["count"]} for row in trend_rows],
        "hotspots": [{"location": row["location_name"], "count": row["count"]} for row in hotspot_rows],
        "rating": rating,
    })


# ---------------------------------------------------------------------------
# Notifications API Endpoint
# ---------------------------------------------------------------------------

@api_bp.route("/api/notifications", methods=["GET"])
def notifications_get():
    user, err = require_auth()
    if err:
        return err

    category = session.get("department") if user["role"] == "authority" else None
    unread = notification_model.get_unread_count(user["id"], category=category)
    notifications = notification_model.get_notifications_for_user(user["id"], category=category)

    return jsonify({
        "unread_count": unread,
        "notifications": [dict(n) for n in notifications],
    })


@api_bp.route("/api/notifications/read", methods=["POST"])
def notifications_mark_read():
    user, err = require_auth()
    if err:
        return err

    category = session.get("department") if user["role"] == "authority" else None
    notification_model.mark_all_read(user["id"], category=category)
    return jsonify({"success": True, "message": "All notifications marked as read."})


# ---------------------------------------------------------------------------
# Contact API Endpoint
# ---------------------------------------------------------------------------

@api_bp.route("/api/contact", methods=["POST"])
def contact_submit():
    data = request.get_json(silent=True) or request.form
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    department = data.get("department", "General").strip()
    message = data.get("message", "").strip()

    if not name or not email or not message:
        return jsonify({"error": "Bad Request", "message": "Name, email, and message are required."}), 400

    user_id = session.get("user_id")
    msg_id = contact_model.create_contact_message(
        user_id=user_id,
        name=name,
        email=email,
        department=department,
        message=message,
    )
    return jsonify({
        "success": True,
        "message": "Your message has been received. We will get back to you soon.",
        "message_id": msg_id,
    }), 201


# ---------------------------------------------------------------------------
# Static Uploads Serving
# ---------------------------------------------------------------------------

@api_bp.route("/uploads/<folder>/<filename>", methods=["GET"])
def serve_upload(folder, filename):
    if folder == "resolved_photos":
        dir_path = current_app.config["UPLOAD_FOLDER_RESOLVED"]
    else:
        dir_path = current_app.config["UPLOAD_FOLDER_ISSUES"]
    return send_from_directory(dir_path, filename)
