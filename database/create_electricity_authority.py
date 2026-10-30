import sys
sys.path.append('backend')
from app import create_app
from app.models.user import create_user
from app.models.authority import create_authority_profile

app = create_app()
with app.app_context():
    user_id = create_user(
        "Ramesh Iyer",
        "electricity@example.com",
        "9900000005",
        "Admin@123",
        "authority"
    )
    create_authority_profile(user_id, "BESCOM - Electricity", "Junior Engineer")
    print("Electricity authority created!")