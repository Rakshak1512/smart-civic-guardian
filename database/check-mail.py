import sys
sys.path.append('backend')
from app.config import Config

print("Username:", Config.MAIL_USERNAME)
print("Password length:", len(Config.MAIL_PASSWORD) if Config.MAIL_PASSWORD else "NOT SET")
print("Password repr:", repr(Config.MAIL_PASSWORD))