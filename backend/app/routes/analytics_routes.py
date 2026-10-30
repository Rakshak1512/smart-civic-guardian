from flask import Blueprint, render_template, jsonify, session
from app.routes.auth_routes import role_required
from app.models import issue as issue_model

analytics_bp = Blueprint("analytics", __name__)

@analytics_bp.route("/admin/analytics")
@role_required("authority", "admin")
def analytics_page():
    return render_template("admin/analytics.html")

@analytics_bp.route("/api/analytics/summary")
@role_required("authority", "admin")
def analytics_summary():
    department_category = session.get("department")
    stats = issue_model.get_stats(category=department_category)
    category_rows = issue_model.get_category_breakdown(category=department_category)
    status_rows = issue_model.get_status_breakdown(category=department_category)
    priority_rows = issue_model.get_priority_breakdown(category=department_category)
    trend_rows = issue_model.get_trend_last_days(14, category=department_category)
    hotspot_rows = issue_model.get_hotspot_locations(5, category=department_category)
    rating = issue_model.get_average_rating(category=department_category)

    return jsonify({
        "stats": stats,
        "by_category": {row["category"]: row["count"] for row in category_rows},
        "by_status": {row["status"]: row["count"] for row in status_rows},
        "by_priority": {row["priority"]: row["count"] for row in priority_rows},
        "trend": [{"day": row["day"], "count": row["count"]} for row in trend_rows],
        "hotspots": [{"location": row["location_name"], "count": row["count"]} for row in hotspot_rows],
        "rating": rating,
    })
