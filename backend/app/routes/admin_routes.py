"""
Authority/Admin routes: dashboard, complaint management (view/filter/search/
assign/status update/resolved photo upload), and map view.
Integrated with Supabase Storage and Supabase PostgreSQL.
"""

import os
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, current_app
)

from app.routes.auth_routes import role_required, EMAIL_RE
from app.models import issue as issue_model
from app.models import user as user_model
from app.services import notification_service, storage_service
from app.models import contact_message as contact_model
from app.models import notification as notification_model
from app.models import authority as authority_model
from app.services.notification_service import CATEGORY_DEPARTMENT_KEYWORDS


admin_bp = Blueprint("admin", __name__)

CIVIC_CATEGORIES = ["Garbage", "Water Leakage", "Electricity Issue", "Pothole"]


@admin_bp.route("/admin/dashboard")
@role_required("authority")
def dashboard():
    department_category = session.get("department")
    filters = {"category": department_category} if department_category else None
    stats = issue_model.get_stats(category=department_category)
    recent = issue_model.get_all_complaints(filters)[:8]
    return render_template("admin/dashboard.html", stats=stats, recent=recent)


@admin_bp.route("/admin/complaints")
@role_required("authority")
def manage_complaints():
    department_category = session.get("department")
    filters = {
        "status": request.args.get("status", ""),
        "category": department_category or request.args.get("category", ""),
        "priority": request.args.get("priority", ""),
        "search": request.args.get("search", ""),
    }
    complaints = issue_model.get_all_complaints(filters)
    return render_template("admin/manage_complaints.html", complaints=complaints, filters=filters)


@admin_bp.route("/admin/complaints/<int:complaint_id>")
@role_required("authority")
def complaint_detail(complaint_id):
    complaint = issue_model.get_complaint_by_id(complaint_id)
    if not complaint:
        flash("Complaint not found.", "error")
        return redirect(url_for("admin.manage_complaints"))

    authorities = user_model.get_all_authorities()
    feedback = issue_model.get_feedback_for_complaint(complaint_id)
    return render_template(
        "admin/complaint_detail.html",
        complaint=complaint,
        authorities=authorities,
        feedback=feedback,
    )


@admin_bp.route("/admin/complaints/<int:complaint_id>/assign", methods=["POST"])
@role_required("authority")
def assign_complaint(complaint_id):
    assignee_id = request.form.get("assigned_to")
    if not assignee_id:
        flash("Please select an authority to assign.", "error")
        return redirect(url_for("admin.complaint_detail", complaint_id=complaint_id))

    issue_model.update_status(complaint_id, "In Progress", assigned_to=int(assignee_id))

    complaint = issue_model.get_complaint_by_id(complaint_id)
    notification_service.notify_assigned(
        int(assignee_id), complaint_id, complaint["category"], complaint.get("location_name", "")
    )

    flash("Complaint assigned successfully.", "success")
    return redirect(url_for("admin.complaint_detail", complaint_id=complaint_id))


@admin_bp.route("/admin/complaints/<int:complaint_id>/status", methods=["POST"])
@role_required("authority")
def update_status(complaint_id):
    complaint = issue_model.get_complaint_by_id(complaint_id)
    if not complaint:
        flash("Complaint not found.", "error")
        return redirect(url_for("admin.manage_complaints"))

    new_status = request.form.get("status")
    resolution_notes = request.form.get("resolution_notes", "").strip()

    if new_status not in ("Pending", "In Progress", "Resolved"):
        flash("Invalid status selected.", "error")
        return redirect(url_for("admin.complaint_detail", complaint_id=complaint_id))

    resolved_photo_path = None
    if new_status == "Resolved":
        photo = request.files.get("resolved_photo")
        if photo and photo.filename:
            try:
                filename = storage_service.save_photo(photo, folder_type="resolved_photos")
                resolved_photo_path = filename
            except ValueError as e:
                flash(str(e), "error")
                return redirect(url_for("admin.complaint_detail", complaint_id=complaint_id))
        elif not complaint.get("resolved_photo_path"):
            flash("Please upload a resolved photo as proof before marking as Resolved.", "error")
            return redirect(url_for("admin.complaint_detail", complaint_id=complaint_id))

    issue_model.update_status(
        complaint_id,
        new_status,
        resolution_notes=resolution_notes or None,
        resolved_photo_path=resolved_photo_path,
    )

    notification_service.notify_status_change(
        complaint_id, complaint["user_id"], complaint["category"], new_status
    )

    flash(f"Complaint status updated to '{new_status}'.", "success")
    return redirect(url_for("admin.complaint_detail", complaint_id=complaint_id))


@admin_bp.route("/admin/map")
@role_required("authority")
def complaints_map():
    complaints = issue_model.get_complaints_for_map()
    department_category = session.get("department")
    if department_category:
        complaints = [c for c in complaints if c.get("category") == department_category]
    return render_template("admin/map.html", complaints=complaints)


@admin_bp.route("/admin/panel")
@role_required("admin")
def admin_panel():
    stats = issue_model.get_stats()
    all_complaints = issue_model.get_all_complaints()
    all_authorities = user_model.get_authority_accounts()
    all_citizens = user_model.get_users_by_role("citizen")
    return render_template(
        "admin/admin_panel.html",
        stats=stats,
        complaints=all_complaints,
        authorities=all_authorities,
        citizens=all_citizens,
    )


@admin_bp.route("/admin/messages")
@role_required("admin")
def view_messages():
    messages = contact_model.get_all_messages()
    return render_template("admin/messages.html", messages=messages)


@admin_bp.route("/admin/messages/<int:message_id>/reply", methods=["POST"])
@role_required("admin")
def reply_message(message_id):
    message_row = contact_model.get_message_by_id(message_id)
    if not message_row:
        flash("Message not found.", "error")
        return redirect(url_for("admin.view_messages"))

    reply_text = request.form.get("reply_text", "").strip()
    if not reply_text:
        flash("Please enter a reply.", "error")
        return redirect(url_for("admin.view_messages"))

    contact_model.save_reply(message_id, reply_text)

    if message_row.get("user_id"):
        notification_model.create_notification(
            message_row["user_id"],
            f"Admin replied to your message: \"{reply_text[:80]}\""
        )

    flash("Reply sent successfully.", "success")
    return redirect(url_for("admin.view_messages"))


@admin_bp.route("/admin/authorities/add", methods=["POST"])
@role_required("admin")
def add_authority():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    department = request.form.get("department", "").strip()
    designation = request.form.get("designation", "").strip() or "Officer"

    errors = []
    if not name:
        errors.append("Name is required.")
    if not EMAIL_RE.match(email):
        errors.append("Please enter a valid email address.")
    if len(password) < 6:
        errors.append("Password must be at least 6 characters long.")
    if department not in ("Garbage", "Water Leakage", "Electricity Issue", "Pothole"):
        errors.append("Please select a department.")
    if not errors and user_model.email_exists(email):
        errors.append("An account with this email already exists.")

    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for("admin.admin_panel"))

    keyword = CATEGORY_DEPARTMENT_KEYWORDS.get(department)
    department_text = f"{keyword} - {department}" if keyword else department

    user_id = user_model.create_user(name, email, "", password, "authority")
    authority_model.create_authority_profile(user_id, department_text, designation)

    flash(f"Authority '{name}' added successfully.", "success")
    return redirect(url_for("admin.admin_panel"))


@admin_bp.route("/admin/authorities/<int:user_id>/remove", methods=["POST"])
@role_required("admin")
def remove_authority(user_id):
    target = user_model.get_user_by_id(user_id)
    if not target or target.get("role") != "authority":
        flash("Authority not found.", "error")
        return redirect(url_for("admin.admin_panel"))

    unassigned = user_model.count_assigned_complaints(user_id)
    user_model.delete_authority(user_id)

    msg = f"Authority '{target['name']}' removed."
    if unassigned:
        msg += f" {unassigned} complaint(s) are now unassigned."
    flash(msg, "success")
    return redirect(url_for("admin.admin_panel"))


@admin_bp.route("/admin/departments")
@role_required("admin")
def departments():
    dept_data = []
    for category in CIVIC_CATEGORIES:
        stats = issue_model.get_stats(category=category)
        officers = user_model.get_authorities_by_department_keyword(category)
        dept_data.append({
            "category": category,
            "authority_name": CATEGORY_DEPARTMENT_KEYWORDS.get(category, ""),
            "stats": stats,
            "officers": officers,
        })
    return render_template("admin/departments.html", departments=dept_data)


@admin_bp.route("/admin/users")
@role_required("admin")
def users():
    citizens = user_model.get_users_by_role("citizen")
    authorities = user_model.get_authority_accounts()
    return render_template("admin/users.html", citizens=citizens, authorities=authorities)


@admin_bp.route("/admin/feedback")
@role_required("authority", "admin")
def feedback_list():
    department_category = session.get("department") if session.get("role") == "authority" else None
    feedback = issue_model.get_all_feedback(category=department_category)
    rating = issue_model.get_average_rating(category=department_category)
    return render_template("admin/feedback.html", feedback=feedback, rating=rating)
