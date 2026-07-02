#!/usr/bin/env python3
"""
One-time OAuth flow to get Google Calendar refresh token.

Usage:
    python scripts/google_oauth.py
    → Opens browser for authorization
    → Prints GOOGLE_REFRESH_TOKEN to stdout
    → Copy it into .env

You must have GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env first.
"""

import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.config import settings


def main():
    if not settings.google_client_id or not settings.google_client_secret:
        print("ERROR: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in .env", file=sys.stderr)
        sys.exit(1)

    # Create a flow with the credentials we have
    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost:8080/"],
            }
        },
        scopes=["https://www.googleapis.com/auth/calendar.events"],
    )

    # Run the local server (opens browser)
    creds = flow.run_local_server(port=8080)

    print(f"\nGOOGLE_REFRESH_TOKEN={creds.refresh_token}")
    print("\nCopy the above line and add it to your .env file, then restart uvicorn.")


if __name__ == "__main__":
    main()
