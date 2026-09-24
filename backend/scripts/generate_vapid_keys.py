"""
Generate the VAPID key pair for web push. Run ONCE, locally:

    python scripts/generate_vapid_keys.py

Then set the three printed values as Railway variables on the daily-tracker
service. The private key is a secret: it goes into Railway and nowhere else —
not into .env committed anywhere, not into a chat, not into the database.
Re-running creates a new pair, which silently invalidates every existing
subscription (the phone would have to re-enable notifications).
"""

import base64

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def main() -> None:
    vapid = Vapid()
    vapid.generate_keys()
    private_raw = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
    public_raw = vapid.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    print("VAPID_PUBLIC_KEY=" + b64url(public_raw))
    print("VAPID_PRIVATE_KEY=" + b64url(private_raw))
    print("VAPID_SUBJECT=mailto:you@example.com   # replace with your own address")


if __name__ == "__main__":
    main()
