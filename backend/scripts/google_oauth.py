#!/usr/bin/env python3
"""
One-time OAuth flow to get Google Calendar refresh token.

Usage:
    python scripts/google_oauth.py
    → Prints an authorization URL to open in your browser
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
                "redirect_uris": ["http://127.0.0.1:8080/"],
            }
        },
        scopes=["https://www.googleapis.com/auth/calendar.events"],
    )

    # Print the authorization URL and wait for the IPv4 loopback callback.
    creds = flow.run_local_server(
        host="127.0.0.1",
        port=8080,
        open_browser=False,
        prompt="consent",
    )

    if not creds.refresh_token:
        print(
            "ERROR: Google did not issue a refresh token. Revoke the app's existing "
            "Google Account access and try again.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"\nGOOGLE_REFRESH_TOKEN={creds.refresh_token}")
    print("\nCopy the above line and add it to your .env file, then restart uvicorn.")


if __name__ == "__main__":
    main()
