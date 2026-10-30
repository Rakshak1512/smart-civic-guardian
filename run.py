"""
Smart Civic Guardian - Unified Full-Stack Application Entry Point
Hosts both the complete website and REST API on a single URL.
Suitable for local running and Vercel cloud deployment.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import create_app

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")

    print("============================================================")
    print("  Smart Civic Guardian - Full-Stack Application             ")
    print("  Database: Supabase PostgreSQL (dkjqzqznubizkjewfeyp)      ")
    print("  Storage : Supabase Private Storage (images)               ")
    print(f"  * Website URL  : http://{host}:{port}/                    ")
    print(f"  * API Health   : http://{host}:{port}/api/health          ")
    print(f"  * API Docs     : http://{host}:{port}/api                 ")
    print("============================================================")
    app.run(debug=debug, host=host, port=port)

