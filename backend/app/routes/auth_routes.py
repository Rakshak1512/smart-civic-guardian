"""
Authentication routes for Smart Civic Guardian.
Includes registration with 6-digit Email OTP verification,
login with role-based routing and demo accounts,
and forgot password with 6-digit Email OTP verification.
All database records are stored directly in Supabase PostgreSQL.
"""

import re
from datetime import datetime, timedelta
from functools import wraps
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, jsonify
)

from app.models import user as user_model
from app.models import authority as authority_model
from app.models import password_reset as reset_model
from app.models import contact_message as contact_model
from app.services import otp_service

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9]{10,15}$")


def validate_password_strength(password):
    """Enforces password policy: at least 6 characters/digits."""
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters."
    return True, None


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to continue.", "error")
                return redirect(url_for("auth.login"))
            user_role = session.get("role")
            if user_role not in roles:
                flash("You do not have permission to view that page.", "error")
                if user_role == "admin":
                    return redirect(url_for("admin.admin_panel"))
                elif user_role == "authority":
                    return redirect(url_for("admin.dashboard"))
                elif user_role == "citizen":
                    return redirect(url_for("issue.my_complaints"))
                return redirect(url_for("auth.login"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Public Information Pages
# ---------------------------------------------------------------------------

@auth_bp.route("/home")
def home():
    if "user_id" in session:
        return redirect(url_for("auth.dashboard_redirect"))
    return render_template("home.html")


@auth_bp.route("/about")
def about():
    return render_template("about.html")


@auth_bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        department = request.form.get("department", "").strip()
        message_text = request.form.get("message", "").strip()

        valid_departments = ("Garbage", "Water Leakage", "Electricity Issue", "Pothole")

        if not name or not EMAIL_RE.match(email) or not message_text:
            flash("Please fill in all fields with a valid email.", "error")
            return render_template("contact.html", form=request.form)

        if department not in valid_departments:
            flash("Please select a valid department.", "error")
            return render_template("contact.html", form=request.form)

        user_id = session.get("user_id")
        contact_model.create_message(user_id, name, email, department, message_text)

        from app.services import notification_service
        notification_service.notify_new_contact_message(name, department)

        flash("Thanks for reaching out! We'll get back to you soon.", "success")
        return redirect(url_for("auth.contact"))

    return render_template("contact.html")


@auth_bp.route("/dashboard")
@login_required
def dashboard_redirect():
    role = session.get("role")
    if role == "admin":
        return redirect(url_for("admin.admin_panel"))
    if role == "authority":
        return redirect(url_for("admin.dashboard"))
    if role == "citizen":
        return redirect(url_for("issue.my_complaints"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@role_required("citizen")
def profile():
    from app.models import issue as issue_model
    from app.db import get_supabase_client
    user_id = session["user_id"]

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()

        if not name:
            flash("Name cannot be empty.", "error")
        else:
            client = get_supabase_client()
            client.table("users").update({"name": name, "phone": phone}).eq("id", user_id).execute()
            session["name"] = name
            flash("Profile updated successfully.", "success")
        return redirect(url_for("auth.profile"))

    user_row = user_model.get_user_by_id(user_id)
    complaints = issue_model.get_complaints_by_user(user_id)
    return render_template("citizen/profile.html", user=user_row, complaints=complaints)


# ---------------------------------------------------------------------------
# Registration with Email OTP Verification
# ---------------------------------------------------------------------------

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("auth/register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")
    role = request.form.get("role", "citizen")
    department = request.form.get("department", "").strip()
    designation = request.form.get("designation", "").strip()
    age_raw = request.form.get("age", "").strip()
    description = request.form.get("description", "").strip()

    errors = []
    if not name:
        errors.append("Full name is required.")
    if not EMAIL_RE.match(email):
        errors.append("Please enter a valid email address.")
    if phone and not PHONE_RE.match(phone):
        errors.append("Please enter a valid 10-digit phone number.")

    is_strong, pwd_err = validate_password_strength(password)
    if not is_strong:
        errors.append(pwd_err)
    if password != confirm_password:
        errors.append("Passwords do not match.")

    if role not in ("citizen", "authority"):
        errors.append("Invalid role selected.")
    if role == "authority" and not department:
        errors.append("Department is required for authority accounts.")

    age = None
    if age_raw:
        if not age_raw.isdigit() or not (1 <= int(age_raw) <= 120):
            errors.append("Please enter a valid age (1-120).")
        else:
            age = int(age_raw)

    if not errors and user_model.email_exists(email):
        errors.append("An account with this email address already exists. Please log in.")

    if errors:
        for err in errors:
            flash(err, "error")
        return render_template("auth/register.html", form=request.form)

    # Generate 6-digit OTP and store HMAC-SHA256 digest with server-side OTP_PEPPER in Supabase PostgreSQL
    otp_code = otp_service.generate_otp()
    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=otp_service.OTP_EXPIRY_MINUTES)
    ok, challenge_id, store_err = otp_service.store_otp_challenge(email, otp_code, purpose="registration")

    # Send plaintext OTP strictly via SMTP email
    sent, mail_err = otp_service.send_otp_email(email, otp_code, purpose="Registration Verification")
    if not sent:
        flash(f"Could not send verification email: {mail_err}. Please verify your email address.", "error")
        return render_template("auth/register.html", form=request.form)

    session["pending_registration"] = {
        "name": name,
        "email": email,
        "phone": phone,
        "password": password,
        "role": role,
        "department": department,
        "designation": designation,
        "age": age,
        "description": description if role == "citizen" else "",
        "challenge_id": challenge_id,
        "expires_at": expires_at.isoformat(),
        "attempts": 0,
        "last_sent": now.isoformat(),
    }

    flash(f"A 6-digit verification code has been sent to {email}. Please enter it below to complete registration.", "success")
    return redirect(url_for("auth.verify_otp"))


@auth_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    pending = session.get("pending_registration")
    if not pending:
        flash("No pending registration found. Please register first.", "error")
        return redirect(url_for("auth.register"))

    if request.method == "GET":
        return render_template(
            "auth/verify_otp.html",
            email=pending["email"],
            expires_at=pending["expires_at"],
            cooldown=otp_service.RESEND_COOLDOWN_SECONDS,
        )

    # Collect entered OTP (either combined field or 6 individual digit inputs)
    entered_otp = request.form.get("otp", "").strip()
    if not entered_otp:
        digits = [request.form.get(f"digit_{i}", "").strip() for i in range(1, 7)]
        entered_otp = "".join(digits)

    if not entered_otp or len(entered_otp) != 6 or not entered_otp.isdigit():
        flash("Please enter all 6 digits of the verification code.", "error")
        return render_template(
            "auth/verify_otp.html",
            email=pending["email"],
            expires_at=pending["expires_at"],
            cooldown=otp_service.RESEND_COOLDOWN_SECONDS,
        )

    # Expiry Check
    try:
        exp_dt = datetime.fromisoformat(pending["expires_at"])
        if datetime.utcnow() > exp_dt:
            flash("Verification code has expired. Please click 'Resend OTP' to get a new code.", "error")
            return render_template(
                "auth/verify_otp.html",
                email=pending["email"],
                expires_at=pending["expires_at"],
                cooldown=0,
            )
    except Exception:
        pass

    # Verify Peppered HMAC Digest from Supabase PostgreSQL email_otps table
    verified, verify_msg = otp_service.verify_stored_otp(pending["email"], entered_otp, purpose="registration")
    if not verified:
        flash(verify_msg, "error")
        return render_template(
            "auth/verify_otp.html",
            email=pending["email"],
            expires_at=pending["expires_at"],
            cooldown=otp_service.RESEND_COOLDOWN_SECONDS,
        )

    # Successfully Verified! Create user in Supabase PostgreSQL
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
            department=pending.get("department", "Sanitation"),
            designation=pending.get("designation") or "Officer",
        )

    session.pop("pending_registration", None)
    flash("Email verified successfully! Your account has been created. Please log in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/resend-otp", methods=["POST"])
def resend_otp():
    pending = session.get("pending_registration")
    if not pending:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            return jsonify({"status": "error", "message": "No active registration session."}), 400
        flash("Registration session expired. Please register again.", "error")
        return redirect(url_for("auth.register"))

    now = datetime.utcnow()
    last_sent_str = pending.get("last_sent")
    if last_sent_str:
        try:
            last_sent = datetime.fromisoformat(last_sent_str)
            elapsed = (now - last_sent).total_seconds()
            if elapsed < otp_service.RESEND_COOLDOWN_SECONDS:
                remaining = int(otp_service.RESEND_COOLDOWN_SECONDS - elapsed)
                msg = f"Please wait {remaining} seconds before requesting a new code."
                if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
                    return jsonify({"status": "error", "message": msg, "retry_after": remaining}), 429
                flash(msg, "warning")
                return redirect(url_for("auth.verify_otp"))
        except Exception:
            pass

    # Issue fresh 6-digit OTP and store HMAC-SHA256 in Supabase PostgreSQL
    otp_code = otp_service.generate_otp()
    ok, challenge_id, store_err = otp_service.store_otp_challenge(pending["email"], otp_code, purpose="registration")
    expires_at = now + timedelta(minutes=otp_service.OTP_EXPIRY_MINUTES)

    sent, mail_err = otp_service.send_otp_email(pending["email"], otp_code, purpose="Registration Verification")
    if not sent:
        msg = f"Failed to send email: {mail_err}"
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            return jsonify({"status": "error", "message": msg}), 500
        flash(msg, "error")
        return redirect(url_for("auth.verify_otp"))

    pending["challenge_id"] = challenge_id
    pending["expires_at"] = expires_at.isoformat()
    pending["last_sent"] = now.isoformat()
    pending["attempts"] = 0
    session["pending_registration"] = pending

    success_msg = f"A new 6-digit verification code has been sent to {pending['email']}."
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify({"status": "success", "message": success_msg, "expires_at": pending["expires_at"]})

    flash(success_msg, "success")
    return redirect(url_for("auth.verify_otp"))


# ---------------------------------------------------------------------------
# Login / Logout with Demo Accounts
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("auth/login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    department = request.form.get("department", "").strip()

    user_row = user_model.get_user_by_email(email)

    if not user_row or not user_model.verify_password(user_row, password):
        flash("Invalid email or password.", "error")
        return render_template("auth/login.html", form=request.form)

    if user_row["role"] == "authority":
        valid_departments = ("Garbage", "Water Leakage", "Electricity Issue", "Pothole")
        if department and department in valid_departments:
            session["department"] = department
        else:
            # Look up profile department if not selected
            prof = authority_model.get_authority_profile(user_row["id"])
            if prof and prof.get("department"):
                session["department"] = prof["department"]

    session["user_id"] = user_row["id"]
    session["name"] = user_row["name"]
    session["role"] = user_row["role"]

    flash(f"Welcome back, {user_row['name']}!", "success")
    return redirect(url_for("auth.dashboard_redirect"))


@auth_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "GET":
        return render_template("admin/admin_login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user_row = user_model.get_user_by_email(email)

    if not user_row or not user_model.verify_password(user_row, password):
        flash("Invalid email or password.", "error")
        return render_template("admin/admin_login.html")

    if user_row["role"] != "admin":
        flash("This portal is for system administrators only.", "error")
        return render_template("admin/admin_login.html")

    session.clear()
    session["user_id"] = user_row["id"]
    session["name"] = user_row["name"]
    session["role"] = user_row["role"]
    flash(f"Welcome back Administrator, {user_row['name']}!", "success")
    return redirect(url_for("admin.admin_panel"))


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("auth.login"))


# ---------------------------------------------------------------------------
# Forgot Password & Reset with 6-Digit Email OTP
# ---------------------------------------------------------------------------

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("auth/forgot_password.html")

    email = request.form.get("email", "").strip().lower()
    if not email or not EMAIL_RE.match(email):
        flash("Please enter a valid email address.", "error")
        return render_template("auth/forgot_password.html")

    user_row = user_model.get_user_by_email(email)

    if user_row:
        otp_code = otp_service.generate_otp()
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=otp_service.OTP_EXPIRY_MINUTES)

        # Store HMAC-SHA256 digest in Supabase PostgreSQL email_otps table
        ok, challenge_id, store_err = otp_service.store_otp_challenge(email, otp_code, purpose="password_reset")

        sent, mail_err = otp_service.send_otp_email(email, otp_code, purpose="Password Reset")
        if not sent:
            flash(f"Could not send email: {mail_err}. Please try again later.", "error")
            return render_template("auth/forgot_password.html")

        session["reset_state"] = {
            "user_id": user_row["id"],
            "email": email,
            "challenge_id": challenge_id,
            "expires_at": expires_at.isoformat(),
            "attempts": 0,
            "last_sent": now.isoformat(),
        }

        flash(f"A 6-digit verification code has been sent to {email}.", "success")
        return redirect(url_for("auth.verify_reset_otp"))

    # If email does not exist, show generic safe message to prevent email enumeration
    flash("If an account exists with that email, a 6-digit verification code has been sent.", "info")
    return render_template("auth/forgot_password.html")


@auth_bp.route("/verify-reset-otp", methods=["GET", "POST"])
def verify_reset_otp():
    state = session.get("reset_state")
    if not state:
        flash("Password reset session expired. Please start again.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "GET":
        return render_template(
            "auth/verify_reset_otp.html",
            email=state["email"],
            expires_at=state["expires_at"],
            cooldown=otp_service.RESEND_COOLDOWN_SECONDS,
        )

    # Collect entered OTP
    entered_otp = request.form.get("otp", "").strip()
    if not entered_otp:
        digits = [request.form.get(f"digit_{i}", "").strip() for i in range(1, 7)]
        entered_otp = "".join(digits)

    if not entered_otp or len(entered_otp) != 6 or not entered_otp.isdigit():
        flash("Please enter all 6 digits of the verification code.", "error")
        return render_template(
            "auth/verify_reset_otp.html",
            email=state["email"],
            expires_at=state["expires_at"],
            cooldown=otp_service.RESEND_COOLDOWN_SECONDS,
        )

    # Check expiry
    try:
        exp_dt = datetime.fromisoformat(state["expires_at"])
        if datetime.utcnow() > exp_dt:
            flash("Verification code has expired. Please click 'Resend OTP'.", "error")
            return render_template(
                "auth/verify_reset_otp.html",
                email=state["email"],
                expires_at=state["expires_at"],
                cooldown=0,
            )
    except Exception:
        pass

    # Verify Peppered HMAC-SHA256 from PostgreSQL email_otps table
    verified, verify_msg = otp_service.verify_stored_otp(state["email"], entered_otp, purpose="password_reset")
    if not verified:
        flash(verify_msg, "error")
        return render_template(
            "auth/verify_reset_otp.html",
            email=state["email"],
            expires_at=state["expires_at"],
            cooldown=otp_service.RESEND_COOLDOWN_SECONDS,
        )

    # Set verified state
    session["verified_reset_user_id"] = state["user_id"]
    session.pop("reset_state", None)

    flash("Code verified successfully! You may now create a new password.", "success")
    return redirect(url_for("auth.reset_password"))


@auth_bp.route("/resend-reset-otp", methods=["POST"])
def resend_reset_otp():
    state = session.get("reset_state")
    if not state:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            return jsonify({"status": "error", "message": "No active password reset session."}), 400
        flash("Password reset session expired. Please start again.", "error")
        return redirect(url_for("auth.forgot_password"))

    now = datetime.utcnow()
    last_sent_str = state.get("last_sent")
    if last_sent_str:
        try:
            last_sent = datetime.fromisoformat(last_sent_str)
            elapsed = (now - last_sent).total_seconds()
            if elapsed < otp_service.RESEND_COOLDOWN_SECONDS:
                remaining = int(otp_service.RESEND_COOLDOWN_SECONDS - elapsed)
                msg = f"Please wait {remaining} seconds before requesting a new code."
                if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
                    return jsonify({"status": "error", "message": msg, "retry_after": remaining}), 429
                flash(msg, "warning")
                return redirect(url_for("auth.verify_reset_otp"))
        except Exception:
            pass

    # Issue fresh 6-digit OTP and store HMAC in PostgreSQL
    otp_code = otp_service.generate_otp()
    ok, challenge_id, store_err = otp_service.store_otp_challenge(state["email"], otp_code, purpose="password_reset")
    expires_at = now + timedelta(minutes=otp_service.OTP_EXPIRY_MINUTES)

    sent, mail_err = otp_service.send_otp_email(state["email"], otp_code, purpose="Password Reset")
    if not sent:
        msg = f"Failed to send email: {mail_err}"
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            return jsonify({"status": "error", "message": msg}), 500
        flash(msg, "error")
        return redirect(url_for("auth.verify_reset_otp"))

    state["challenge_id"] = challenge_id
    state["expires_at"] = expires_at.isoformat()
    state["last_sent"] = now.isoformat()
    state["attempts"] = 0
    session["reset_state"] = state

    success_msg = f"A new 6-digit verification code has been sent to {state['email']}."
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify({"status": "success", "message": success_msg, "expires_at": state["expires_at"]})

    flash(success_msg, "success")
    return redirect(url_for("auth.verify_reset_otp"))


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    user_id = session.get("verified_reset_user_id")
    if not user_id:
        flash("Unauthorized access. Please verify your OTP code first.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "GET":
        return render_template("auth/reset_password.html")

    new_password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    is_strong, pwd_err = validate_password_strength(new_password)
    if not is_strong:
        flash(pwd_err, "error")
        return render_template("auth/reset_password.html")

    if new_password != confirm_password:
        flash("Passwords do not match.", "error")
        return render_template("auth/reset_password.html")

    # Update password in Supabase PostgreSQL
    user_model.update_password(user_id, new_password)
    session.pop("verified_reset_user_id", None)

    flash("Password changed successfully! You can now log in with your new password.", "success")
    return redirect(url_for("auth.login"))
