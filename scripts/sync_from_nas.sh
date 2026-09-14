#!/usr/bin/env bash
set -euo pipefail

# PhotoSynApp - Sync Photos from Synology NAS to Cortex (/Workspaces/Photos)
# Usage: ./scripts/sync_from_nas.sh [laura|paul|historical|all]

TARGET="${1:-all}"
DEST_BASE="/Workspaces/Photos"

mkdir -p "$DEST_BASE/Laura_Only" "$DEST_BASE/Paul_Combined" "$DEST_BASE/Historical_Master"

sync_laura() {
    echo "=========================================================="
    echo "Syncing Laura's Photos (NAS -> Cortex)..."
    echo "Source: synology:/volume1/PhotoSync/Laura/ALL_PHOTOS/"
    echo "Dest:   $DEST_BASE/Laura_Only/"
    echo "=========================================================="
    rsync -avh --info=progress2 --stats synology:/volume1/PhotoSync/Laura/ALL_PHOTOS/ "$DEST_BASE/Laura_Only/"
}

sync_paul() {
    echo "=========================================================="
    echo "Syncing Paul's Combined Photos (NAS -> Cortex)..."
    echo "Source: synology:/volume1/PhotoSync/ALL_PHOTOS/"
    echo "Dest:   $DEST_BASE/Paul_Combined/"
    echo "=========================================================="
    rsync -avh --info=progress2 --stats synology:/volume1/PhotoSync/ALL_PHOTOS/ "$DEST_BASE/Paul_Combined/"
}

sync_historical() {
    echo "=========================================================="
    echo "Syncing Historical Master Photos (NAS -> Cortex)..."
    echo "Source: synology:/volume1/Photos/"
    echo "Dest:   $DEST_BASE/Historical_Master/"
    echo "=========================================================="
    rsync -avh --info=progress2 --stats --exclude '@eaDir' --exclude '#recycle' synology:/volume1/Photos/ "$DEST_BASE/Historical_Master/"
}

case "$TARGET" in
    laura)
        sync_laura
        ;;
    paul)
        sync_paul
        ;;
    historical)
        sync_historical
        ;;
    all)
        sync_laura
        sync_paul
        sync_historical
        ;;
    *)
        echo "Unknown target: $TARGET. Choose: laura, paul, historical, or all."
        exit 1
        ;;
esac

echo ""
echo "Sync completed successfully at $(date)!"
