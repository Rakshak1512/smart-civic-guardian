"""
Seeds the database with demo accounts and sample complaints the first
time the app runs (i.e. when civic_guardian.db does not yet exist),
so the dashboards and analytics can be demonstrated immediately.
"""

import random
from datetime import datetime, timedelta

from app.models import user as user_model
from app.models import authority as authority_model
from app.models import issue as issue_model
from app.models import notification as notification_model
from app.db import get_db


DEMO_LOCATIONS = [
    ("MG Road, Bengaluru", 12.9758, 77.6045),
    ("Indiranagar 100ft Road, Bengaluru", 12.9719, 77.6412),
    ("Koramangala 5th Block, Bengaluru", 12.9352, 77.6245),
    ("Whitefield Main Road, Bengaluru", 12.9698, 77.7500),
    ("Jayanagar 4th Block, Bengaluru", 12.9308, 77.5838),
    ("HSR Layout Sector 2, Bengaluru", 12.9116, 77.6389),
]

CATEGORIES = ["Garbage", "Water Leakage", "Electricity Issue", "Pothole"]
PRIORITIES = ["Low", "Medium", "High"]

SAMPLE_DESCRIPTIONS = {
    "Garbage": "Garbage has been piling up on the roadside for several days and is not being collected.",
    "Water Leakage": "There is a continuous water leak from an underground pipe near the footpath.",
    "Electricity Issue": "A street light pole has exposed wiring which looks hazardous at night.",
    "Pothole": "A large pothole has formed on the main road causing trouble for vehicles.",
}


def seed_demo_data(app):
    with app.app_context():
        db = get_db()

        # Demo users
        citizen1_id = user_model.create_user("Anita Rao", "citizen@example.com", "9900000001", "Citizen@123", "citizen")
        citizen2_id = user_model.create_user("Ravi Kumar", "citizen2@example.com", "9900000002", "Citizen@123", "citizen")

        admin1_id = user_model.create_user("Suresh Patil", "admin@example.com", "9900000003", "Admin@123", "authority")
        authority_model.create_authority_profile(admin1_id, "BBMP - Sanitation & Roads", "Junior Engineer")

        admin2_id = user_model.create_user("Deepa Shetty", "water@example.com", "9900000004", "Admin@123", "authority")
        authority_model.create_authority_profile(admin2_id, "BWSSB - Water Supply", "Assistant Engineer")

        citizens = [citizen1_id, citizen2_id]
        statuses = ["Pending", "In Progress", "Resolved"]

        # Sample complaints with varied category/priority/status/location/date
        for i in range(14):
            category = CATEGORIES[i % len(CATEGORIES)]
            location_name, lat, lon = random.choice(DEMO_LOCATIONS)
            priority = PRIORITIES[i % len(PRIORITIES)]
            status = statuses[i % len(statuses)]
            user_id = citizens[i % len(citizens)]
            days_ago = random.randint(0, 20)

            complaint_id = issue_model.create_complaint({
                "user_id": user_id,
                "category": category,
                "ai_detected_category": category,
                "ai_confidence": round(random.uniform(0.6, 0.92), 2),
                "description": SAMPLE_DESCRIPTIONS[category],
                "photo_path": None,
                "latitude": lat,
                "longitude": lon,
                "location_name": location_name,
                "priority": priority,
            })

            created_at = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
            db.execute(
                "UPDATE complaints SET created_at = ?, updated_at = ? WHERE id = ?",
                (created_at, created_at, complaint_id),
            )

            if status in ("In Progress", "Resolved"):
                assigned = admin1_id if category != "Water Leakage" else admin2_id
                resolved_photo = "uploads/resolved_photos/demo_resolved.jpg" if status == "Resolved" else None
                notes = "Issue verified and work order raised." if status == "In Progress" else "Issue fixed and verified on-site."
                db.execute(
                    """UPDATE complaints SET status = ?, assigned_to = ?, resolution_notes = ?,
                       resolved_photo_path = ?, resolved_at = ? WHERE id = ?""",
                    (
                        status,
                        assigned,
                        notes,
                        resolved_photo,
                        created_at if status == "Resolved" else None,
                        complaint_id,
                    ),
                )
                notification_model.create_notification(
                    user_id, f"Your complaint ({category}) status: {status}.", complaint_id
                )

            if status == "Resolved" and random.random() > 0.4:
                issue_model.add_feedback(
                    complaint_id, user_id, random.randint(3, 5), "Thanks for resolving this quickly."
                )

            notification_model.create_notification(
                admin1_id if category != "Water Leakage" else admin2_id,
                f"New civic complaint reported: {category} - {priority} Priority ({location_name})",
                complaint_id,
            )

        db.commit()
