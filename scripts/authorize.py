"""One-time OAuth setup.

Run this on a machine with a browser -- NOT on the headless NAS. It opens a
local server on your PC to complete the Google OAuth flow, then writes a
token.json you copy over to the NAS config folder (the path referenced by
`drive.token_path` in config.yaml).

Usage:
    pip install google-auth-oauthlib
    python scripts/authorize.py --client-secret client_secret.json --out token.json
"""

from __future__ import annotations

import argparse

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--client-secret",
        required=True,
        help="Path to the OAuth client secret JSON downloaded from Google Cloud Console.",
    )
    parser.add_argument("--out", default="token.json")
    args = parser.parse_args()

    flow = InstalledAppFlow.from_client_secrets_file(args.client_secret, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(args.out, "w") as f:
        f.write(creds.to_json())

    print(f"Wrote {args.out} -- copy this file to your NAS config folder.")


if __name__ == "__main__":
    main()
