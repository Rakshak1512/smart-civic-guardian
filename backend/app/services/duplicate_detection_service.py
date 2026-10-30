"""
Duplicate Detection Service
----------------------------
Checks whether a newly submitted complaint matches an existing one
(same category, nearby location, submitted recently). If so, the new
complaint is linked to the existing one instead of being treated as a
brand-new independent issue, and the existing complaint's support count
and priority may increase to reflect community impact.
"""

from flask import current_app
from app.models import issue as issue_model
from app.services.location_service import haversine_distance_meters


def find_duplicate(category, latitude, longitude, location_name):
    """
    Returns the matching existing complaint row if a duplicate is found,
    otherwise None.
    Matching rule: same category AND (within DUPLICATE_DISTANCE_METERS OR
    same location_name text) AND reported within the last 30 days.
    """
    candidates = issue_model.get_recent_complaints_for_duplicate_check(category, days=30)
    max_distance = current_app.config.get("DUPLICATE_DISTANCE_METERS", 150)

    for candidate in candidates:
        distance = haversine_distance_meters(
            latitude, longitude, candidate["latitude"], candidate["longitude"]
        )
        same_named_location = (
            location_name
            and candidate["location_name"]
            and location_name.strip().lower() == candidate["location_name"].strip().lower()
        )

        if (distance is not None and distance <= max_distance) or same_named_location:
            return candidate

    return None


def escalate_priority_if_needed(complaint):
    """
    Once support_count grows, bump priority up a level (capped at High)
    to reflect that more citizens are affected by the same issue.
    """
    count = complaint["support_count"] + 1  # +1 for the new duplicate report
    current_priority = complaint["priority"]

    if count >= 5:
        return "High"
    if count >= 3 and current_priority == "Low":
        return "Medium"
    return current_priority
