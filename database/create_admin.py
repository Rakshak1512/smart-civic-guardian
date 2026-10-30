import sys
sys.path.append('backend')
from app import create_app
from app.models.user import create_user

app = create_app()
with app.app_context():
    create_user("Admin User", "admin@test.com", "9999999999", "admin123", "admin")

print("Admin created!")