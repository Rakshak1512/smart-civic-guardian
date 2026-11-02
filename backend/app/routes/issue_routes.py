"""
Citizen-facing routes: report a new issue, view own complaints,
track status, view notifications, and submit feedback/rating.
Integrated with Supabase Storage and Supabase PostgreSQL.
"""

import os
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, jsonify, current_app
)

from app.routes.auth_routes import login_required, role_required
from app.models import issue as issue_model
from app.models import notification as notification_model
from app.services import ai_detection_service, duplicate_detection_service
from app.services import location_service, notification_service
from app.services import storage_service
from app.models import user as user_model

issue_bp = Blueprint("issue", __name__)


@issue_bp.route("/report-issue/analyze", methods=["POST"])
@role_required("citizen")
def analyze_photo():
    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    latitude = request.form.get("latitude", "").strip()
    longitude = request.form.get("longitude", "").strip()
    location_name = request.form.get("location_name", "").strip()
    manual_location = request.form.get("manual_location", "").strip()
    device_latitude = request.form.get("device_latitude", "").strip()
    device_longitude = request.form.get("device_longitude", "").strip()
    location_accuracy = request.form.get("location_accuracy", "").strip()
    location_source = request.form.get("location_source", "").strip()
    photo = request.files.get("photo")

    errors = []
    if category not in ("Garbage", "Water Leakage", "Electricity Issue", "Pothole"):
        errors.append("Please select a valid category.")
    if len(description) < 10:
        errors.append("Please provide a description of at least 10 characters.")
    if not photo or photo.filename == "":
        errors.append("Please upload a photo of the issue.")

    if errors:
        for e in errors:
            flash(e, "error")
        return render_template("citizen/report_issue.html", form=request.form)

    # Analyse the incoming bytes before storage consumes the upload stream.
    try:
        photo.stream.seek(0)
        ai_result = ai_detection_service.detect_category(user_selected_category=category, image_file=photo)
    except Exception:
        ai_result = ai_detection_service.detect_category(user_selected_category=category)

    try:
        photo.stream.seek(0)
        photo_key = storage_service.save_photo(photo, folder_type="issue_photos")
    except ValueError as e:
        flash(str(e), "error")
        return render_template("citizen/report_issue.html", form=request.form)

    photo_path = photo_key
    loc = location_service.resolve_location(
        latitude, longitude, location_name, manual_location,
        accuracy=location_accuracy, location_source=location_source,
        device_lat=device_latitude, device_lon=device_longitude
    )
    # Use the AI suggestion for duplicate lookup only when reliable; otherwise
    # retain the citizen's selected/manual category.
    detected_category = ai_result.get("category") if ai_result.get("reliable") else category
    duplicate = duplicate_detection_service.find_duplicate(
        detected_category, loc["latitude"], loc["longitude"], loc["location_name"]
    )

    return render_template(
        "citizen/report_issue.html",
        ai_result=ai_result,
        ai_suggested_category=(ai_result.get("category") if ai_result.get("reliable") else category),
        duplicate=duplicate,
        photo_filename=photo_key,
        photo_path=photo_path,
        category=category,
        description=description,
        latitude=loc["latitude"],
        longitude=loc["longitude"],
        location_name=loc["location_name"],
        manual_location=manual_location,
        device_latitude=device_latitude,
        device_longitude=device_longitude,
        location_accuracy=location_accuracy,
        location_source=location_source,
    )


@issue_bp.route("/report-issue", methods=["GET", "POST"])
@role_required("citizen")
def report_issue():
    if request.method == "GET":
        return render_template("citizen/report_issue.html")

    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    latitude = request.form.get("latitude", "").strip()
    longitude = request.form.get("longitude", "").strip()
    location_name = request.form.get("location_name", "").strip()
    manual_location = request.form.get("manual_location", "").strip()
    device_latitude = request.form.get("device_latitude", "").strip()
    device_longitude = request.form.get("device_longitude", "").strip()
    location_accuracy = request.form.get("location_accuracy", "").strip()
    location_source = request.form.get("location_source", "").strip()
    analyzed_photo = request.form.get("analyzed_photo", "").strip()
    submitted_ai_category = request.form.get("ai_detected_category", "").strip()
    submitted_ai_confidence = request.form.get("ai_confidence", "0").strip()
    photo = request.files.get("photo")

    errors = []
    if category not in ("Garbage", "Water Leakage", "Electricity Issue", "Pothole"):
        errors.append("Please select a valid category.")
    if len(description) < 10:
        errors.append("Please provide a description of at least 10 characters.")
    if not location_service.is_valid_coordinate(latitude, longitude) and not manual_location.strip():
        errors.append("Please capture device GPS location or enter a precise location/landmark.")
    if not analyzed_photo and (not photo or photo.filename == ""):
        errors.append("Please upload and analyze a photo of the issue.")

    if errors:
        for e in errors:
            flash(e, "error")
        return render_template("citizen/report_issue.html", form=request.form)

    if analyzed_photo:
        # Never trust an arbitrary client-supplied storage path. It must be the
        # opaque key created during the previous authenticated analysis step.
        # The analysis flow already stores the image and passes the key back.
        photo_key = analyzed_photo
    else:
        try:
            photo_key = storage_service.save_photo(photo, folder_type="issue_photos")
        except ValueError as e:
            flash(str(e), "error")
            return render_template("citizen/report_issue.html", form=request.form)

    photo_path = photo_key

    # Resolve GPS / location
    loc = location_service.resolve_location(
        latitude, longitude, location_name, manual_location,
        accuracy=location_accuracy, location_source=location_source,
        device_lat=device_latitude, device_lon=device_longitude
    )

    # Keep the independently analysed result from the review step. If a citizen
    # submitted without the analysis step, preserve their manual category.
    try:
        confidence = max(0.0, min(1.0, float(submitted_ai_confidence)))
    except (TypeError, ValueError):
        confidence = 0.0
    if submitted_ai_category in ("Garbage", "Water Leakage", "Electricity Issue", "Pothole") and confidence > 0:
        ai_result = {
            "category": submitted_ai_category,
            "confidence": confidence,
            "priority": ai_detection_service._calculate_base_priority(submitted_ai_category, confidence),
            "reliable": confidence >= 0.65,
        }
    else:
        ai_result = {
            "category": None, "confidence": 0.0,
            "priority": ai_detection_service._calculate_base_priority(category, 0.0),
            "reliable": False,
        }
    detected_category = ai_result.get("category") if ai_result.get("reliable") else category
    duplicate = duplicate_detection_service.find_duplicate(
        detected_category, loc["latitude"], loc["longitude"], loc["location_name"]
    )

    priority = ai_result.get("priority", "Medium")
    duplicate_of = None
    duplicate_group = None

    if duplicate:
        duplicate_of = duplicate["id"]
        duplicate_group = duplicate.get("duplicate_group") or f"group-{duplicate['id']}"
        priority = duplicate_detection_service.escalate_priority_if_needed(duplicate)
        issue_model.update_status(duplicate["id"], duplicate["status"])
        issue_model.increment_support_count(duplicate["id"])

    complaint_id = issue_model.create_complaint({
        "user_id": session["user_id"],
        "category": category,
        "ai_detected_category": ai_result.get("category") or category,
        "ai_confidence": ai_result.get("confidence", 0.0),
        "description": description,
        "photo_path": photo_path,
        "latitude": loc["latitude"],
        "longitude": loc["longitude"],
        "location_name": loc["location_name"],
        "priority": priority,
        "duplicate_of": duplicate_of,
        "duplicate_group": duplicate_group,
    })

    # Auto-assign to responsible department authority
    from app.services.notification_service import CATEGORY_DEPARTMENT_KEYWORDS
    keyword = CATEGORY_DEPARTMENT_KEYWORDS.get(category)
    if keyword:
        matching = user_model.get_authorities_by_department_keyword(keyword)
        if matching:
            issue_model.update_status(complaint_id, "Pending", assigned_to=matching[0]["id"])

    notification_service.notify_new_complaint(complaint_id, category, priority, loc["location_name"])
    if duplicate:
        notification_service.notify_duplicate_linked(session["user_id"], complaint_id, category)
    else:
        notification_service.notify_complaint_submitted(session["user_id"], complaint_id, category, priority)

    flash("Complaint submitted successfully! You can track its progress in 'My Complaints'.", "success")
    return redirect(url_for("issue.my_complaints"))


@issue_bp.route("/my-complaints")
@role_required("citizen")
def my_complaints():
    complaints = issue_model.get_complaints_by_user(session["user_id"])
    return render_template("citizen/my_complaints.html", complaints=complaints)


@issue_bp.route("/track-status")
@role_required("citizen")
def track_status_list():
    return redirect(url_for("issue.my_complaints"))


@issue_bp.route("/track-status/<int:complaint_id>")
@role_required("citizen")
def track_status(complaint_id):
    complaint = issue_model.get_complaint_by_id(complaint_id)
    if not complaint or complaint["user_id"] != session["user_id"]:
        flash("Complaint not found or you do not have access to it.", "error")
        return redirect(url_for("issue.my_complaints"))

    feedback = issue_model.get_feedback_for_complaint(complaint_id)
    return render_template("citizen/track_status.html", complaint=complaint, feedback=feedback)


@issue_bp.route("/submit-feedback/<int:complaint_id>", methods=["POST"])
@role_required("citizen")
def submit_feedback(complaint_id):
    complaint = issue_model.get_complaint_by_id(complaint_id)
    if not complaint or complaint["user_id"] != session["user_id"]:
        flash("Complaint not found or you do not have access to it.", "error")
        return redirect(url_for("issue.my_complaints"))

    if complaint["status"] != "Resolved":
        flash("Feedback can only be submitted after a complaint is resolved.", "error")
        return redirect(url_for("issue.track_status", complaint_id=complaint_id))

    try:
        rating = int(request.form.get("rating", 0))
        if not (1 <= rating <= 5):
            raise ValueError
    except ValueError:
        flash("Please select a valid rating between 1 and 5.", "error")
        return redirect(url_for("issue.track_status", complaint_id=complaint_id))

    comment = request.form.get("comment", "").strip()
    issue_model.add_feedback(complaint_id, session["user_id"], rating, comment)
    flash("Thank you for your feedback!", "success")
    return redirect(url_for("issue.track_status", complaint_id=complaint_id))


@issue_bp.route("/my-feedback")
@role_required("citizen")
def my_feedback():
    feedback = issue_model.get_feedback_by_user(session["user_id"])
    return render_template("citizen/my_feedback.html", feedback=feedback)


@issue_bp.route("/notifications")
@login_required
def notifications():
    category = session.get("department") if session.get("role") == "authority" else None
    notes = notification_model.get_notifications_for_user(session["user_id"], category=category)
    notification_model.mark_all_read(session["user_id"])
    return render_template("shared/notifications.html", notifications=notes)


@issue_bp.route("/api/notifications/unread-count")
@login_required
def unread_count():
    category = session.get("department") if session.get("role") == "authority" else None
    count = notification_model.get_unread_count(session["user_id"], category=category)
    return jsonify({"count": count})


@issue_bp.route("/civic-map")
@role_required("citizen")
def civic_map():
    complaints = issue_model.get_complaints_for_map()
    return render_template("citizen/civic_map.html", complaints=complaints)
