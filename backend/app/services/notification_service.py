"""
Notification Service
---------------------
Central place that creates the notification messages sent to citizens
and authorities. Wraps the notification model so routes don't need to
build message strings themselves.
"""

from app.models import notification as notification_model
from app.models import user as user_model

CATEGORY_DEPARTMENT_KEYWORDS = {
    "Garbage": "BBMP",
    "Pothole": "BBMP",
    "Electricity Issue": "BESCOM",
    "Water Leakage": "BWSSB",
}


def notify_new_complaint(complaint_id, category, priority, location_name):
    """Notify the authority department responsible for this category.
    Falls back to notifying every authority if no matching department exists."""
    message = f"New civic complaint reported: {category} - {priority} Priority ({location_name})"

    keyword = CATEGORY_DEPARTMENT_KEYWORDS.get(category)
    authorities = user_model.get_authorities_by_department_keyword(keyword) if keyword else []
    if not authorities:
        authorities = user_model.get_all_authorities()

    for authority in authorities:
        notification_model.create_notification(authority["id"], message, complaint_id)


def notify_status_change(complaint_id, citizen_id, category, new_status):
    """Notify the citizen who filed the complaint whenever its status changes."""
    friendly = {
        "Pending": "is Pending review",
        "In Progress": "is now In Progress",
        "Resolved": "has been Resolved",
    }.get(new_status, f"status changed to {new_status}")

    message = f"Your complaint ({category}) {friendly}."
    notification_model.create_notification(citizen_id, message, complaint_id)


def notify_complaint_submitted(citizen_id, complaint_id, category, priority):
    """Confirm to the citizen that their complaint was received."""
    message = f"Your complaint ({category}, {priority} Priority) has been submitted and is Pending review."
    notification_model.create_notification(citizen_id, message, complaint_id)

def notify_duplicate_linked(citizen_id, complaint_id, category):
    """Let a citizen know their report matched an existing tracked issue."""
    message = f"Your {category} report matched an existing complaint in your area and has been linked to it."
    notification_model.create_notification(citizen_id, message, complaint_id)

def notify_new_contact_message(sender_name, department):
    """Notify every admin account when a new contact message is submitted."""
    message = f"New contact message from {sender_name} ({department})."
    admins = user_model.get_users_by_role("admin")
    for admin in admins:
        notification_model.create_notification(admin["id"], message)
