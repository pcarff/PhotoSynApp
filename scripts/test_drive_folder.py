"""Helper script to test access to a shared Google Drive folder."""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.drive_client import DriveClient
from app.takeout_group import group_takeout_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Test access to a shared Google Drive folder")
    parser.add_argument("folder_id", help="The Google Drive folder ID (from the share link)")
    parser.add_argument(
        "--token", default="config/token.json", help="Path to token.json (default: config/token.json)"
    )
    args = parser.parse_args()

    token_path = Path(args.token)
    if not token_path.exists():
        print(f"Error: Token file not found at {token_path}")
        sys.exit(1)

    print(f"Connecting to Google Drive using {token_path}...")
    client = DriveClient(token_path)

    try:
        folder_meta = (
            client._service.files()
            .get(
                fileId=args.folder_id,
                fields="id, name, owners, shared, permissions",
                supportsAllDrives=True,
            )
            .execute()
        )
    except Exception as e:
        print(f"\nError: Could not access folder ID '{args.folder_id}': {e}")
        print("Please check that:")
        print(" 1. The folder ID is correct.")
        print(" 2. Laura shared the folder with the Google account associated with token.json.")
        sys.exit(1)

    owner_names = [o.get("displayName", o.get("emailAddress", "Unknown")) for o in folder_meta.get("owners", [])]
    print(f"\nSuccess! Folder found:")
    print(f"  Folder Name: {folder_meta.get('name')}")
    print(f"  Folder ID:   {folder_meta.get('id')}")
    print(f"  Owner:       {', '.join(owner_names)}")
    print(f"  Shared:      {folder_meta.get('shared', False)}")

    print("\nScanning for files inside folder...")
    drive_files = client.list_takeout_files(args.folder_id)
    print(f"Found {len(drive_files)} file(s) in folder:")

    for f in drive_files:
        print(f"  - {f.name} (modified: {f.modified_time})")

    groups = group_takeout_files(drive_files)
    if groups:
        print(f"\nIdentified {len(groups)} Takeout export group(s):")
        for g in groups:
            print(f"  Export ID: {g.export_id} ({len(g.files)} parts)")
            for sf in g.sorted_files():
                print(f"    -> {sf.name}")
    else:
        print("\nNote: No matching 'takeout-*.zip' files found in this folder yet.")
        if drive_files:
            print("Files present did not match the expected Takeout filename pattern.")


if __name__ == "__main__":
    main()
