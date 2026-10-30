"""
Smart Civic Guardian - Dedicated Backend REST API Service
"""

import os
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import create_app

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")

    print("============================================================")
    print("  Smart Civic Guardian - Dedicated REST API Backend Server  ")
    print(f"  * Status       : Running                                  ")
    print(f"  * Backend URL  : http://{host}:{port}/                    ")
    print(f"  * API Health   : http://{host}:{port}/api/health          ")
    print(f"  * API Docs     : http://{host}:{port}/api                 ")
    print(f"  * CORS Allowed : {app.config.get('CORS_ORIGINS')}         ")
    print("============================================================")
    app.run(debug=debug, host=host, port=port)
