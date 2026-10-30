"""
Frontend Service Entry Point for Smart Civic Guardian.
Runs the frontend web application on port 3000.
"""

import os
import sys

# Ensure frontend directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import app, FRONTEND_URL, BACKEND_URL, PORT, HOST, IS_PRODUCTION

if __name__ == "__main__":
    print("============================================================")
    print("  Smart Civic Guardian - Dedicated Frontend Service         ")
    print(f"  * Status        : Online                                  ")
    print(f"  * Frontend Web  : {FRONTEND_URL}                          ")
    print(f"  * Calling API   : {BACKEND_URL}                           ")
    print("============================================================")
    app.run(debug=not IS_PRODUCTION, host=HOST, port=PORT)
